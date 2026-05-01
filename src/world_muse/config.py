from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_PROVIDER = "mock"
DEFAULT_MODEL = "mock-world-muse-v1"
DEFAULT_STYLE = "Dramatic"
DEFAULT_PROVIDERS = ["mock", "openai"]
DEFAULT_STYLES = ["Dramatic", "Relaxed", "Urgent", "Suspenseful", "Comedic", "Lurid", "Horror"]
DEFAULT_MODELS_BY_PROVIDER = {
    "mock": ["mock-world-muse-v1"],
    "openai": ["gpt-4.1"],
}


@dataclass
class AppSettings:
    current_story_project: str = "my-story"
    current_world: str = ""
    current_provider: str = DEFAULT_PROVIDER
    current_model: str = DEFAULT_MODEL
    current_style: str = DEFAULT_STYLE
    use_ai_questions: bool = True
    agent_foundry_executable: str = "agentfoundry"
    agent_foundry_working_directory: str = field(default_factory=lambda: default_agent_foundry_project_dir())
    world_roots: list[str] = field(default_factory=lambda: default_world_roots())
    providers: list[str] = field(default_factory=lambda: list(DEFAULT_PROVIDERS))
    styles: list[str] = field(default_factory=lambda: list(DEFAULT_STYLES))
    models_by_provider: dict[str, list[str]] = field(
        default_factory=lambda: {key: list(value) for key, value in DEFAULT_MODELS_BY_PROVIDER.items()}
    )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AppSettings":
        defaults = cls()
        world_roots = payload.get("world_roots", defaults.world_roots)
        providers = payload.get("providers", defaults.providers)
        styles = payload.get("styles", defaults.styles)
        models_by_provider = payload.get("models_by_provider", defaults.models_by_provider)
        normalized_styles = [str(item) for item in styles] if isinstance(styles, list) and styles else defaults.styles
        configured_style = str(payload.get("current_style", defaults.current_style))
        return cls(
            current_story_project=str(payload.get("current_story_project", defaults.current_story_project)),
            current_world=str(payload.get("current_world", defaults.current_world)),
            current_provider=str(payload.get("current_provider", defaults.current_provider)),
            current_model=str(payload.get("current_model", defaults.current_model)),
            current_style=configured_style if configured_style in normalized_styles else normalized_styles[0],
            use_ai_questions=bool(payload.get("use_ai_questions", defaults.use_ai_questions)),
            agent_foundry_executable=str(
                payload.get("agent_foundry_executable", defaults.agent_foundry_executable)
            ),
            agent_foundry_working_directory=str(
                payload.get("agent_foundry_working_directory", defaults.agent_foundry_working_directory)
            ),
            world_roots=[str(item) for item in world_roots] if isinstance(world_roots, list) else defaults.world_roots,
            providers=[str(item) for item in providers] if isinstance(providers, list) else defaults.providers,
            styles=normalized_styles,
            models_by_provider=normalize_models_by_provider(models_by_provider, defaults.models_by_provider),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def model_options(self, provider: str | None = None) -> list[str]:
        selected_provider = provider or self.current_provider
        options = self.models_by_provider.get(selected_provider, [])
        if options:
            return options
        return [self.current_model] if self.current_model else []


@dataclass(frozen=True)
class WorldInfo:
    id: str
    title: str
    path: Path

    @property
    def label(self) -> str:
        return f"{self.title} ({self.id})" if self.title and self.title != self.id else self.id


def default_world_roots() -> list[str]:
    return [
        str(Path.cwd() / "worlds"),
        "/home/ubuntu/projects/worldcodex/worlds",
    ]


def default_agent_foundry_project_dir() -> str:
    candidates = [
        Path("/home/ubuntu/projects/kadathic_core/src"),
        Path("/home/ubuntu/projects/agent_foundry"),
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return ""


def normalize_models_by_provider(value: Any, fallback: dict[str, list[str]]) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {key: list(items) for key, items in fallback.items()}
    result: dict[str, list[str]] = {}
    for key, items in value.items():
        if isinstance(items, list):
            result[str(key)] = [str(item) for item in items]
    return result or {key: list(items) for key, items in fallback.items()}


def default_config_dir(project_root: Path | None = None) -> Path:
    return (project_root or Path.cwd()) / "config"


def app_settings_path(config_dir: Path) -> Path:
    return config_dir / "app_settings.json"


def load_settings(config_dir: Path | None = None) -> AppSettings:
    resolved_dir = config_dir or default_config_dir()
    path = app_settings_path(resolved_dir)
    if not path.exists():
        settings = AppSettings()
        save_settings(settings, resolved_dir)
        return settings
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return AppSettings.from_dict(payload)


def save_settings(settings: AppSettings, config_dir: Path | None = None) -> Path:
    resolved_dir = config_dir or default_config_dir()
    resolved_dir.mkdir(parents=True, exist_ok=True)
    path = app_settings_path(resolved_dir)
    path.write_text(json.dumps(settings.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def update_selection(
    settings: AppSettings,
    *,
    story_project: str | None = None,
    world: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    style: str | None = None,
    use_ai_questions: bool | None = None,
) -> AppSettings:
    if story_project is not None:
        settings.current_story_project = story_project
    if world is not None:
        settings.current_world = world
    if provider is not None:
        settings.current_provider = provider
    if model is not None:
        settings.current_model = model
    if style is not None:
        settings.current_style = style
    if use_ai_questions is not None:
        settings.use_ai_questions = use_ai_questions
    return settings


def discover_worlds(world_roots: list[str]) -> list[WorldInfo]:
    worlds: list[WorldInfo] = []
    seen: set[Path] = set()
    for raw_root in world_roots:
        root = Path(raw_root).expanduser()
        if not root.exists() or not root.is_dir():
            continue
        candidates = [root] if (root / "world.toml").exists() else sorted(root.iterdir())
        for candidate in candidates:
            if not candidate.is_dir() or candidate in seen:
                continue
            world_toml = candidate / "world.toml"
            if not world_toml.exists():
                continue
            seen.add(candidate)
            worlds.append(read_world_info(candidate, world_toml))
    return sorted(worlds, key=lambda item: item.label.lower())


def read_world_info(path: Path, world_toml: Path) -> WorldInfo:
    text = world_toml.read_text(encoding="utf-8")
    world_id = extract_toml_string(text, "id") or path.name
    title = extract_toml_string(text, "title") or world_id
    return WorldInfo(id=world_id, title=title, path=path)


def extract_toml_string(text: str, key: str) -> str | None:
    match = re.search(rf"^\s*{re.escape(key)}\s*=\s*['\"]([^'\"]+)['\"]", text, re.MULTILINE)
    return match.group(1).strip() if match else None
