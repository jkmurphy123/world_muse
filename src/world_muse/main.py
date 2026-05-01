from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Callable

from .adapters.agent_foundry import run_llm_connection_test
from .command_runner import SubprocessCommandRunner
from .config import AppSettings, default_config_dir, discover_worlds, load_settings, save_settings, update_selection
from .state import StoryNode, default_story_structure, find_node_by_id
from .status import StatusLog


def build_app(*, config_dir: Path | None = None) -> None:
    try:
        from nicegui import ui
    except ImportError as exc:
        raise RuntimeError("NiceGUI is required to run the GUI. Install with `pip install -e .`.") from exc

    resolved_config_dir = config_dir or default_config_dir(project_root=Path.cwd())
    settings = load_settings(resolved_config_dir)
    runner = SubprocessCommandRunner()
    worlds = discover_worlds(settings.world_roots)
    world_options = [world.id for world in worlds]
    if settings.current_world and settings.current_world not in world_options:
        world_options.append(settings.current_world)
    if not settings.current_world and world_options:
        settings.current_world = world_options[0]
        save_settings(settings, resolved_config_dir)
    structure = default_story_structure()
    status_log = StatusLog()
    status_log.info("Ready.")
    if not world_options:
        status_log.warning("No WorldCodex worlds discovered. Update config/app_settings.json world_roots.")

    @ui.page("/")
    def index() -> None:
        render_layout(
            settings=settings,
            config_dir=resolved_config_dir,
            world_options=world_options,
            structure=structure,
            status_log=status_log,
            runner=runner,
        )


def render_layout(
    *,
    settings: AppSettings,
    config_dir: Path,
    world_options: list[str],
    structure: list[StoryNode],
    status_log: StatusLog,
    runner: SubprocessCommandRunner,
) -> None:
    from nicegui import ui

    available_world_options = list(world_options)
    selected: dict[str, Any] = {"node": structure[0] if structure else None}
    status_renderer: dict[str, Callable[[], None]] = {"render": lambda: None}

    ui.query("body").classes("m-0 overflow-hidden")
    ui.add_head_html(
        """
        <style>
          .top-panel-field .q-field__label,
          .top-panel-field .q-field__native,
          .top-panel-field .q-field__input,
          .top-panel-field .q-field__append,
          .top-panel-field .q-select__dropdown-icon {
            color: white !important;
          }
          .top-panel-field .q-field__control {
            color: white !important;
          }
        </style>
        """
    )
    with ui.column().classes("w-full h-screen gap-0 bg-slate-50"):
        def add_status(level: str, text: str) -> None:
            status_log.add(level, text)
            status_renderer["render"]()
            color = {"info": "positive", "warning": "warning", "error": "negative"}.get(level, "info")
            try:
                ui.notify(text, color=color)
            except RuntimeError:
                # NiceGUI notify can fail when the triggering slot was removed during the same callback.
                pass

        def refresh_world_options(preferred_world: str | None = None) -> None:
            discovered = discover_worlds(settings.world_roots)
            refreshed = [world.id for world in discovered]
            if settings.current_world and settings.current_world not in refreshed:
                refreshed.append(settings.current_world)
            if preferred_world and preferred_world not in refreshed:
                refreshed.append(preferred_world)
            available_world_options.clear()
            available_world_options.extend(refreshed)
            selected_world = preferred_world or settings.current_world or (available_world_options[0] if available_world_options else "")
            if selected_world:
                update_selection(settings, world=selected_world)
                save_settings(settings, config_dir)
            world_options_updater(available_world_options, selected_world or None)

        def load_places_for_current_world() -> tuple[list[dict[str, Any]], str | None]:
            world_id = str(settings.current_world or "").strip()
            if not world_id:
                return [], "No current world selected."
            worldcodex_cwd = resolve_worldcodex_workdir(settings)
            command_with_rebuild = ["world", "get", world_id, "--type", "place", "--pretty", "--rebuild-index"]
            result = runner.run(command_with_rebuild, timeout_seconds=60, cwd=worldcodex_cwd)
            if not result.ok:
                # Fallback for environments where index rebuild is not writable.
                command_without_rebuild = ["world", "get", world_id, "--type", "place", "--pretty"]
                result = runner.run(command_without_rebuild, timeout_seconds=60, cwd=worldcodex_cwd)
            if not result.ok:
                detail = (result.stderr or result.stdout or "unknown error").strip()
                return [], f"WorldCodex get failed: {detail}"
            places = parse_world_get_places(result.stdout)
            if not places and result.stdout.strip():
                return [], "WorldCodex returned no parseable places."
            return places, None

        def open_setting_wizard() -> None:
            setting_node = find_node_by_id(structure, "setting")
            if setting_node is None:
                add_status("error", "Could not locate SETTING node.")
                return
            with ui.dialog() as dialog, ui.card().classes("w-[760px] max-w-full"):
                ui.label("Create Setting").classes("text-lg font-semibold")
                ui.label(f"Current World: {settings.current_world or '(none selected)'}").classes("text-xs text-slate-500")
                place_name_input = ui.input(label="Place Title").classes("w-full")
                place_id_input = ui.input(label="Place ID", value=place_id_from_title("")).classes("w-full")
                place_summary_input = ui.input(label="Summary").classes("w-full")
                place_description_input = ui.textarea(label="Description").classes("w-full").props("autogrow")
                ui.label("Place ID auto-generates from title; you can edit it.").classes("text-xs text-slate-500")

                def sync_place_id(event) -> None:
                    place_id_input.value = place_id_from_title(str(event.value or ""))
                    place_id_input.update()

                place_name_input.on_value_change(sync_place_id)
                with ui.row().classes("w-full justify-end gap-2 pt-2"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")

                    def create_place(*, close_dialog: bool) -> None:
                        world_id = str(settings.current_world or "").strip()
                        place_name = str(place_name_input.value or "").strip()
                        place_id = normalize_place_id(str(place_id_input.value or ""), place_name)
                        place_summary = str(place_summary_input.value or "").strip()
                        place_description = str(place_description_input.value or "").strip()
                        if not world_id:
                            add_status("error", "Choose a current world before creating a setting.")
                            return
                        if not place_name:
                            add_status("error", "Place title is required.")
                            return
                        if not place_id:
                            add_status("error", "Place ID is required.")
                            return
                        worldcodex_cwd = resolve_worldcodex_workdir(settings)
                        command = build_world_add_place_command(
                            world_id=world_id,
                            place_name=place_name,
                            place_id=place_id,
                            summary=place_summary,
                            description=place_description,
                            runner=runner,
                            settings=settings,
                        )
                        result = runner.run(command, timeout_seconds=90, cwd=worldcodex_cwd)
                        if not result.ok:
                            detail = (result.stderr or result.stdout or "unknown error").strip()
                            add_status("error", f"Failed to add place '{place_name}': {detail}")
                            return
                        places, places_error = load_places_for_current_world()
                        if places_error:
                            setting_node.summary = f"Created place {place_name}."
                        else:
                            setting_node.summary = f"{len(places)} place(s) in {world_id}."
                        setting_node.details = {
                            "Current World": world_id,
                            "Last Added Place": place_name,
                            "Last Added Place ID": place_id,
                            "Last Added Summary": place_summary,
                            "Last Added Description": place_description,
                            "Add Command": " ".join(command),
                        }
                        selected["node"] = setting_node
                        render_right_panel()
                        add_status("info", f"Added place '{place_name}' ({place_id}) to {world_id}.")
                        if close_dialog:
                            dialog.close()
                        else:
                            place_name_input.value = ""
                            place_id_input.value = place_id_from_title("")
                            place_summary_input.value = ""
                            place_description_input.value = ""
                            place_name_input.update()
                            place_id_input.update()
                            place_summary_input.update()
                            place_description_input.update()

                    ui.button("Add Another", on_click=lambda: create_place(close_dialog=False)).props("color=secondary")
                    ui.button("Submit", on_click=lambda: create_place(close_dialog=True)).props("color=primary")
            dialog.open()

        def open_world_creator() -> None:
            world_node = find_node_by_id(structure, "premise")
            if world_node is None:
                add_status("error", "Could not locate THE WORLD node.")
                return
            with ui.dialog() as dialog, ui.card().classes("w-[760px] max-w-full"):
                ui.label("Create World Wizard").classes("text-lg font-semibold")
                title_input = ui.input(label="World Title", value=world_node.details.get("World Title", "")).classes("w-full")
                world_id_input = ui.input(
                    label="World ID",
                    value=world_id_from_title(str(title_input.value or "")),
                ).classes("w-full")
                ui.label("World ID is auto-generated from the title; you can edit it before submit.").classes(
                    "text-xs text-slate-500"
                )

                def sync_world_id(event) -> None:
                    typed_title = str(event.value or "")
                    world_id_input.value = world_id_from_title(typed_title)
                    world_id_input.update()

                title_input.on_value_change(sync_world_id)
                with ui.row().classes("w-full justify-end gap-2 pt-2"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")

                    def on_submit_world() -> None:
                        world_title = str(title_input.value or "").strip()
                        world_id = world_id_from_title(str(world_id_input.value or ""))
                        if not world_title:
                            add_status("error", "World title is required.")
                            return
                        if not world_id:
                            add_status("error", "World ID is required.")
                            return
                        worldcodex_cwd = resolve_worldcodex_workdir(settings)
                        command = ["world", "init", world_id, "--title", world_title]
                        result = runner.run(command, timeout_seconds=90, cwd=worldcodex_cwd)
                        if not result.ok:
                            detail = (result.stderr or result.stdout or "unknown error").strip()
                            add_status("error", f"Failed to initialize world '{world_id}': {detail}")
                            return
                        world_node.summary = world_title
                        world_node.details = {
                            "World Title": world_title,
                            "World ID": world_id,
                            "Init Command": " ".join(command),
                        }
                        selected["node"] = world_node
                        refresh_world_options(preferred_world=world_id)
                        render_right_panel()
                        add_status("info", f"World '{world_title}' ({world_id}) initialized and selected.")
                        dialog.close()

                    ui.button("Create World", on_click=on_submit_world).props("color=primary")
            dialog.open()

        def open_character_creator() -> None:
            character_node = find_node_by_id(structure, "characters")
            if character_node is None:
                add_status("error", "Could not locate CHARACTERS node.")
                return
            with ui.dialog() as dialog, ui.card().classes("w-[760px] max-w-full"):
                ui.label("Create Character").classes("text-lg font-semibold")
                name_input = ui.input(label="Character Name").classes("w-full")
                role_input = ui.input(label="Role").classes("w-full")
                motivation_input = ui.textarea(label="Motivation").classes("w-full").props("autogrow")
                conflict_input = ui.textarea(label="Conflict").classes("w-full").props("autogrow")
                with ui.row().classes("w-full justify-end gap-2 pt-2"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")

                    def on_submit_character() -> None:
                        name = str(name_input.value or "").strip() or "Unnamed"
                        role = str(role_input.value or "").strip()
                        motivation = str(motivation_input.value or "").strip()
                        conflict = str(conflict_input.value or "").strip()
                        entry_number = sum(1 for key in character_node.details if key.startswith("Character ")) + 1
                        key = f"Character {entry_number}: {name}"
                        character_node.details[key] = (
                            f"Role: {role or '(unspecified)'}\n"
                            f"Motivation: {motivation or '(unspecified)'}\n"
                            f"Conflict: {conflict or '(unspecified)'}"
                        )
                        character_node.summary = f"{entry_number} character(s) captured."
                        selected["node"] = character_node
                        render_right_panel()
                        add_status("info", f"Character '{name}' added.")
                        dialog.close()

                    ui.button("Add Character", on_click=on_submit_character).props("color=primary")
            dialog.open()

        world_options_updater = top_panel(
            settings,
            config_dir,
            available_world_options,
            add_status,
            runner,
        )
        with ui.row().classes("w-full grow gap-0 overflow-hidden"):
            def on_select(node: StoryNode) -> None:
                selected["node"] = node
                render_right_panel()

            left_panel(structure, on_select=on_select)
            right_container = ui.column().classes("grow h-full overflow-auto p-5")

            def render_right_panel() -> None:
                right_container.clear()
                with right_container:
                    node = selected.get("node")
                    if node is None:
                        ui.label("Select a story node").classes("text-xl font-semibold text-slate-800")
                        return
                    with ui.row().classes("w-full items-center justify-between"):
                        ui.label(node.label).classes("text-xl font-semibold text-slate-800")
                        if node.id == "setting":
                            ui.button("Create Setting", on_click=open_setting_wizard).props("color=primary")
                        elif node.id == "premise":
                            ui.button("Create World", on_click=open_world_creator).props("color=primary")
                        elif node.id == "characters":
                            ui.button("Create Character", on_click=open_character_creator).props("color=primary")
                    ui.label(node.summary or "No details yet.").classes("text-sm text-slate-600")
                    ui.separator().classes("my-2")
                    ui.label(f"Node ID: {node.id}").classes("text-xs text-slate-500")
                    ui.label(f"Children: {len(node.children)}").classes("text-xs text-slate-500")
                    if node.id == "setting":
                        ui.separator().classes("my-2")
                        ui.label(f"WorldCodex Places ({settings.current_world or 'no world selected'})").classes(
                            "text-sm font-semibold text-slate-700"
                        )
                        places, places_error = load_places_for_current_world()
                        if places_error:
                            ui.label(places_error).classes("text-sm text-red-700")
                        elif not places:
                            ui.label("No places found. Use Create Setting to add one.").classes("text-sm text-slate-600")
                        else:
                            for place in places:
                                name = str(place.get("name") or "(unnamed)")
                                atom_id = str(place.get("id") or "(no id)")
                                summary = str(place.get("summary") or "").strip()
                                description = str(place.get("description") or "").strip()
                                ui.label(name).classes("text-sm font-semibold text-slate-700")
                                ui.label(atom_id).classes("text-xs text-slate-500")
                                if summary:
                                    ui.label(summary).classes("text-sm text-slate-700")
                                if description:
                                    ui.label(description).classes("text-sm text-slate-600")
                                ui.separator().classes("my-1")
                    if node.details:
                        ui.separator().classes("my-2")
                        for key, value in node.details.items():
                            ui.label(key).classes("text-xs font-semibold text-slate-600")
                            ui.label(value or "(no response)").classes("text-sm text-slate-700")

            render_right_panel()
        status_renderer["render"] = bottom_panel(status_log)


def top_panel(
    settings: AppSettings,
    config_dir: Path,
    world_options: list[str],
    add_status,
    runner: SubprocessCommandRunner,
) -> Callable[[list[str], str | None], None]:
    from nicegui import ui

    with ui.row().classes("w-full h-16 items-center gap-3 px-4 bg-slate-900 text-white"):
        ui.label("World Muse").classes("text-lg font-semibold min-w-36")
        story_input = ui.input(
            label="Story Project",
            value=settings.current_story_project,
        ).classes("w-56 top-panel-field")
        world_select = ui.select(
            options=world_options,
            value=settings.current_world or (world_options[0] if world_options else None),
            label="Current World",
            with_input=True,
        ).classes("w-64 top-panel-field")
        provider_select = ui.select(
            options=settings.providers,
            value=settings.current_provider,
            label="Provider",
        ).classes("w-40 top-panel-field")
        model_select = ui.select(
            options=settings.model_options(settings.current_provider),
            value=settings.current_model,
            label="Model",
            with_input=True,
        ).classes("w-56 top-panel-field")
        ai_switch = ui.switch("AI Questions", value=settings.use_ai_questions).classes("top-panel-field")

        def save_project() -> None:
            update_selection(settings, story_project=str(story_input.value or ""))
            save_settings(settings, config_dir)
            add_status("info", "Updated story project.")

        def save_world() -> None:
            update_selection(settings, world=str(world_select.value or ""))
            save_settings(settings, config_dir)
            add_status("info", "Updated current world.")

        def save_provider() -> None:
            provider = str(provider_select.value or settings.current_provider)
            model_options = settings.model_options(provider)
            model_select.options = model_options
            if model_options and model_select.value not in model_options:
                model_select.value = model_options[0]
            update_selection(settings, provider=provider, model=str(model_select.value or ""))
            save_settings(settings, config_dir)
            model_select.update()
            add_status("info", f"Provider set to {provider}.")

        def save_model() -> None:
            update_selection(settings, model=str(model_select.value or ""))
            save_settings(settings, config_dir)
            add_status("info", "Updated model.")

        def save_ai_mode() -> None:
            update_selection(settings, use_ai_questions=bool(ai_switch.value))
            save_settings(settings, config_dir)
            add_status("info", f"AI question mode {'enabled' if settings.use_ai_questions else 'disabled'}.")

        def on_test_llm() -> None:
            provider = str(provider_select.value or settings.current_provider)
            model = str(model_select.value or settings.current_model)
            update_selection(settings, provider=provider, model=model)
            save_settings(settings, config_dir)
            result = run_llm_connection_test(
                settings=settings,
                runner=runner,
                provider=provider,
                model=model,
            )
            if result.ok:
                add_status("info", f"LLM connection OK for {provider}/{model}.")
            else:
                detail = (result.result.stderr or result.result.stdout or "unknown error").strip()
                add_status("error", f"LLM connection failed for {provider}/{model}: {detail}")

        story_input.on_value_change(lambda _: save_project())
        world_select.on_value_change(lambda _: save_world())
        provider_select.on_value_change(lambda _: save_provider())
        model_select.on_value_change(lambda _: save_model())
        ai_switch.on_value_change(lambda _: save_ai_mode())
        ui.button("Test LLM", on_click=on_test_llm).props("color=secondary")

        def update_world_options(options: list[str], selected_world: str | None = None) -> None:
            world_select.options = list(options)
            if selected_world:
                world_select.value = selected_world
            elif options:
                world_select.value = options[0]
            else:
                world_select.value = None
            update_selection(settings, world=str(world_select.value or ""))
            save_settings(settings, config_dir)
            world_select.update()

        return update_world_options


def left_panel(structure: list[StoryNode], *, on_select) -> None:
    from nicegui import ui

    with ui.column().classes("w-80 h-full overflow-auto border-r border-slate-200 bg-white p-3"):
        ui.label("World Building").classes("text-sm font-semibold text-slate-600 uppercase")
        for node in structure:
            render_story_node(node, on_select=on_select)


def render_story_node(node: StoryNode, *, on_select) -> None:
    from nicegui import ui

    if not node.children:
        ui.button(node.label, on_click=lambda n=node: on_select(n)).props("flat dense align=left").classes(
            "w-full justify-start"
        )
        return
    with ui.expansion(node.label, value=True).classes("w-full"):
        ui.button(f"View {node.label}", on_click=lambda n=node: on_select(n)).props("flat dense align=left").classes(
            "w-full justify-start"
        )
        for child in node.children:
            render_story_node(child, on_select=on_select)


def bottom_panel(status_log: StatusLog):
    from nicegui import ui

    with ui.column().classes("w-full h-28 overflow-auto border-t border-slate-300 bg-slate-100 px-4 py-2") as container:
        def render() -> None:
            container.clear()
            with container:
                ui.label("Status").classes("text-xs font-semibold uppercase text-slate-500")
                for message in status_log.messages[-10:]:
                    ui.label(f"{message.level.upper()}: {message.text}").classes(status_class(message.level))

        render()
        return render


def status_class(level: str) -> str:
    return {
        "info": "text-sm text-blue-700",
        "warning": "text-sm text-amber-700",
        "error": "text-sm text-red-700",
    }.get(level, "text-sm text-slate-700")


def world_id_from_title(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "new-world"


def place_id_from_title(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return f"place.{slug or 'untitled'}"


def normalize_place_id(value: str, place_title: str) -> str:
    candidate = value.strip().lower()
    if not candidate:
        return place_id_from_title(place_title)
    if "." not in candidate:
        return f"place.{candidate}"
    return candidate


def parse_world_get_places(stdout: str) -> list[dict[str, Any]]:
    text = (stdout or "").strip()
    if not text:
        return []
    payload = parse_json_payload(text)
    if payload is None:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def parse_json_payload(text: str) -> Any | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Some CLIs print non-JSON lines around payload; recover by parsing the first JSON block.
    for open_char, close_char in (("[", "]"), ("{", "}")):
        start = text.find(open_char)
        end = text.rfind(close_char)
        if start == -1 or end == -1 or end <= start:
            continue
        snippet = text[start : end + 1]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            continue
    return None


def world_add_supports_option(*, runner: SubprocessCommandRunner, settings: AppSettings, option: str) -> bool:
    worldcodex_cwd = resolve_worldcodex_workdir(settings)
    help_result = runner.run(["world", "add", "--help"], timeout_seconds=20, cwd=worldcodex_cwd)
    if not help_result.ok:
        return False
    return option in f"{help_result.stdout}\n{help_result.stderr}"


def build_world_add_place_command(
    *,
    world_id: str,
    place_name: str,
    place_id: str,
    summary: str,
    description: str,
    runner: SubprocessCommandRunner,
    settings: AppSettings,
) -> list[str]:
    command = ["world", "add", world_id, "place", place_name, "--id", place_id, "--pretty"]
    has_summary_option = world_add_supports_option(runner=runner, settings=settings, option="--summary")
    has_description_option = world_add_supports_option(runner=runner, settings=settings, option="--description")
    if has_summary_option and summary:
        command.extend(["--summary", summary])
    if has_description_option:
        description_value = description
        if (not has_summary_option) and summary and (not description_value):
            description_value = summary
        if description_value:
            command.extend(["--description", description_value])
    return command


def resolve_worldcodex_workdir(settings: AppSettings) -> Path | None:
    for root in settings.world_roots:
        candidate = Path(root).expanduser()
        if candidate.name != "worlds":
            continue
        project_root = candidate.parent
        if (project_root / "src" / "worldbld" / "cli.py").exists():
            return project_root
    fallback = Path("/home/ubuntu/projects/worldcodex")
    if (fallback / "src" / "worldbld" / "cli.py").exists():
        return fallback
    return None


def main() -> None:
    from nicegui import ui

    build_app()
    ui.run(
        host="127.0.0.1",
        port=int(os.getenv("WORLD_MUSE_PORT", "8080")),
        title="World Muse",
        reload=False,
        show=False,
    )


if __name__ == "__main__":
    main()
