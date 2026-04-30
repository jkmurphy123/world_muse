from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .config import AppSettings, default_config_dir, discover_worlds, load_settings, save_settings, update_selection
from .state import StoryNode, default_story_structure
from .status import StatusLog


def build_app(*, config_dir: Path | None = None) -> None:
    try:
        from nicegui import ui
    except ImportError as exc:
        raise RuntimeError("NiceGUI is required to run the GUI. Install with `pip install -e .`.") from exc

    resolved_config_dir = config_dir or default_config_dir(project_root=Path.cwd())
    settings = load_settings(resolved_config_dir)
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
        )


def render_layout(
    *,
    settings: AppSettings,
    config_dir: Path,
    world_options: list[str],
    structure: list[StoryNode],
    status_log: StatusLog,
) -> None:
    from nicegui import ui

    selected: dict[str, Any] = {"node": structure[0] if structure else None}

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
        top_panel(settings, config_dir, status_log, world_options)
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
                    ui.label(node.label).classes("text-xl font-semibold text-slate-800")
                    ui.label(node.summary or "No details yet.").classes("text-sm text-slate-600")
                    ui.separator().classes("my-2")
                    ui.label(f"Node ID: {node.id}").classes("text-xs text-slate-500")
                    ui.label(f"Children: {len(node.children)}").classes("text-xs text-slate-500")

            render_right_panel()
        bottom_panel(status_log)


def top_panel(
    settings: AppSettings,
    config_dir: Path,
    status_log: StatusLog,
    world_options: list[str],
) -> None:
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

        def save_project() -> None:
            update_selection(settings, story_project=str(story_input.value or ""))
            save_settings(settings, config_dir)
            status_log.info("Updated story project.")

        def save_world() -> None:
            update_selection(settings, world=str(world_select.value or ""))
            save_settings(settings, config_dir)
            status_log.info("Updated current world.")

        def save_provider() -> None:
            provider = str(provider_select.value or settings.current_provider)
            model_options = settings.model_options(provider)
            model_select.options = model_options
            if model_options and model_select.value not in model_options:
                model_select.value = model_options[0]
            update_selection(settings, provider=provider, model=str(model_select.value or ""))
            save_settings(settings, config_dir)
            model_select.update()
            status_log.info(f"Provider set to {provider}.")

        def save_model() -> None:
            update_selection(settings, model=str(model_select.value or ""))
            save_settings(settings, config_dir)
            status_log.info("Updated model.")

        story_input.on_value_change(lambda _: save_project())
        world_select.on_value_change(lambda _: save_world())
        provider_select.on_value_change(lambda _: save_provider())
        model_select.on_value_change(lambda _: save_model())


def left_panel(structure: list[StoryNode], *, on_select) -> None:
    from nicegui import ui

    with ui.column().classes("w-80 h-full overflow-auto border-r border-slate-200 bg-white p-3"):
        ui.label("Story Structure").classes("text-sm font-semibold text-slate-600 uppercase")
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


def bottom_panel(status_log: StatusLog) -> None:
    from nicegui import ui

    with ui.column().classes("w-full h-28 overflow-auto border-t border-slate-300 bg-slate-100 px-4 py-2"):
        ui.label("Status").classes("text-xs font-semibold uppercase text-slate-500")
        for message in status_log.messages[-10:]:
            ui.label(f"{message.level.upper()}: {message.text}").classes(status_class(message.level))


def status_class(level: str) -> str:
    return {
        "info": "text-sm text-blue-700",
        "warning": "text-sm text-amber-700",
        "error": "text-sm text-red-700",
    }.get(level, "text-sm text-slate-700")


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
