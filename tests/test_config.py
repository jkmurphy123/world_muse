from __future__ import annotations

import json

from world_muse.config import (
    app_settings_path,
    discover_worlds,
    load_settings,
    save_settings,
    update_selection,
)


def test_load_settings_creates_defaults_when_missing(tmp_path):
    settings = load_settings(tmp_path)

    assert settings.current_story_project == "my-story"
    assert settings.current_provider == "mock"
    assert settings.current_model == "mock-world-muse-v1"
    assert settings.use_ai_questions is True
    assert settings.agent_foundry_executable == "agentfoundry"
    assert app_settings_path(tmp_path).exists()


def test_save_settings_persists_selected_values(tmp_path):
    settings = load_settings(tmp_path)
    update_selection(
        settings,
        story_project="embers",
        world="titan-osa",
        provider="openai",
        model="gpt-4.1",
    )

    path = save_settings(settings, tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    loaded = load_settings(tmp_path)

    assert payload["current_story_project"] == "embers"
    assert payload["current_world"] == "titan-osa"
    assert loaded.current_provider == "openai"
    assert loaded.current_model == "gpt-4.1"


def test_discover_worlds_finds_world_toml_children(tmp_path):
    worlds_root = tmp_path / "worlds"
    titan = worlds_root / "titan-osa"
    blank = worlds_root / "scratch"
    titan.mkdir(parents=True)
    blank.mkdir()
    (titan / "world.toml").write_text(
        'id = "titan-osa"\ntitle = "Titan Osa"\n',
        encoding="utf-8",
    )

    worlds = discover_worlds([str(worlds_root)])

    assert len(worlds) == 1
    assert worlds[0].id == "titan-osa"
    assert worlds[0].title == "Titan Osa"
    assert worlds[0].path == titan
