from __future__ import annotations


def test_main_module_imports_without_starting_server():
    import world_muse.main as main

    assert callable(main.build_app)
    assert callable(main.main)


def test_world_id_from_title_slugifies():
    import world_muse.main as main

    assert main.world_id_from_title("Argonaut Station (Titan)") == "argonaut-station-titan"
    assert main.world_id_from_title("  ") == "new-world"


def test_place_id_helpers():
    import world_muse.main as main

    assert main.place_id_from_title("Argonaut Station") == "place.argonaut_station"
    assert main.normalize_place_id("", "Argonaut Station") == "place.argonaut_station"
    assert main.normalize_place_id("my_place", "unused") == "place.my_place"
    assert main.normalize_place_id("place.custom_id", "unused") == "place.custom_id"


def test_parse_world_get_places_accepts_list_or_object():
    import world_muse.main as main

    assert main.parse_world_get_places('[{"id":"place.a","name":"A"}]') == [{"id": "place.a", "name": "A"}]
    assert main.parse_world_get_places('{"id":"place.a","name":"A"}') == [{"id": "place.a", "name": "A"}]
    assert main.parse_world_get_places("not json") == []


def test_parse_world_get_places_accepts_wrapped_json_output():
    import world_muse.main as main

    wrapped = "Built index: /tmp/index.json\n[{\"id\":\"place.a\",\"name\":\"A\"}]"
    assert main.parse_world_get_places(wrapped) == [{"id": "place.a", "name": "A"}]


def test_stringify_for_ui_handles_structured_values():
    import world_muse.main as main

    assert main.stringify_for_ui(None) == ""
    assert main.stringify_for_ui("abc") == "abc"
    assert '"a": 1' in main.stringify_for_ui({"a": 1})


def test_clamp_ui_text_truncates_long_values():
    import world_muse.main as main

    text = "x" * 50
    assert main.clamp_ui_text(text, limit=20).endswith("[truncated]")


def test_build_world_add_place_command_uses_summary_and_description_when_available(monkeypatch):
    import world_muse.main as main
    from world_muse.config import AppSettings

    settings = AppSettings()

    class StubRunner:
        def run(self, command, *, timeout_seconds=None, cwd=None):  # noqa: ANN001
            from world_muse.command_runner import CommandResult

            return CommandResult(
                command=tuple(command),
                returncode=0,
                stdout="--summary --description",
                stderr="",
                duration_ms=1,
            )

    cmd = main.build_world_add_place_command(
        world_id="titan-osa",
        place_name="Argonaut Station",
        place_id="place.argonaut_station",
        summary="Core orbital habitat",
        description="Main population center.",
        runner=StubRunner(),
        settings=settings,
    )

    assert "--summary" in cmd
    assert "--description" in cmd


def test_build_world_add_place_command_falls_back_to_description_only():
    import world_muse.main as main
    from world_muse.config import AppSettings

    settings = AppSettings()

    class StubRunner:
        def run(self, command, *, timeout_seconds=None, cwd=None):  # noqa: ANN001
            from world_muse.command_runner import CommandResult

            return CommandResult(
                command=tuple(command),
                returncode=0,
                stdout="--description",
                stderr="",
                duration_ms=1,
            )

    cmd = main.build_world_add_place_command(
        world_id="titan-osa",
        place_name="Argonaut Station",
        place_id="place.argonaut_station",
        summary="Core orbital habitat",
        description="",
        runner=StubRunner(),
        settings=settings,
    )

    assert "--summary" not in cmd
    assert "--description" in cmd
