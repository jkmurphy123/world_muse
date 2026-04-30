from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from ..command_runner import CommandResult, Runner
from ..config import AppSettings


@dataclass(frozen=True)
class AgentFoundryConnectionResult:
    result: CommandResult
    executable: str

    @property
    def ok(self) -> bool:
        return self.result.ok


def resolve_executable(executable: str) -> str:
    if executable and Path(executable).exists():
        return executable

    candidates = [executable, "agentfoundry", "agent-foundry", "agent_foundry"]
    for candidate in candidates:
        if not candidate:
            continue
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    fallback_dirs = [
        Path("/home/ubuntu/projects/kadathic_core/.venv/bin"),
        Path("/home/ubuntu/projects/kadathic_core/src/.venv/bin"),
        Path("/home/ubuntu/projects/agent_foundry/.venv/bin"),
    ]
    for directory in fallback_dirs:
        for candidate in ("agentfoundry", "agent-foundry", "agent_foundry"):
            fallback = directory / candidate
            if fallback.exists():
                return str(fallback)

    return executable


def resolve_working_directory(settings: AppSettings) -> str:
    candidates: list[Path] = []
    if settings.agent_foundry_working_directory:
        candidates.append(Path(settings.agent_foundry_working_directory))
    candidates.extend(
        [
            Path("/home/ubuntu/projects/kadathic_core/src"),
            Path("/home/ubuntu/projects/agent_foundry"),
        ]
    )
    for candidate in candidates:
        if (candidate / "agent_foundry" / "cli" / "main.py").exists():
            return str(candidate)
    return settings.agent_foundry_working_directory or ""


def resolve_command(settings: AppSettings) -> tuple[str, ...]:
    executable = resolve_executable(settings.agent_foundry_executable)
    if executable in {"agent-foundry", "agent_foundry"}:
        canonical = shutil.which("agentfoundry")
        if canonical:
            return (canonical,)
    if executable and shutil.which(executable):
        return (executable,)
    if Path(executable).exists():
        return (executable,)

    resolved_workdir = resolve_working_directory(settings)
    workdir = Path(resolved_workdir) if resolved_workdir else None
    if workdir and (workdir / "agent_foundry" / "cli" / "main.py").exists():
        return (sys.executable, "-m", "agent_foundry.cli.main")

    return (executable,)


def run_llm_connection_test(
    *,
    settings: AppSettings,
    runner: Runner,
    provider: str,
    model: str,
    timeout_seconds: int = 60,
) -> AgentFoundryConnectionResult:
    base = resolve_command(settings)
    cwd = resolve_working_directory(settings) or None
    result = runner.run(
        [
            *base,
            "test-llm-connection",
            "--provider",
            provider,
            "--model",
            model,
        ],
        timeout_seconds=timeout_seconds,
        cwd=cwd,
    )
    return AgentFoundryConnectionResult(result=result, executable=" ".join(base))


def generate_setting_question(
    *,
    settings: AppSettings,
    runner: Runner,
    provider: str,
    model: str,
    step: int,
    total: int,
    previous_answers: list[str],
    fallback_question: str,
    timeout_seconds: int = 45,
) -> str:
    if provider == "mock":
        return build_mock_followup(step=step, total=total, previous_answers=previous_answers, fallback=fallback_question)

    base = resolve_command(settings)
    cwd = resolve_working_directory(settings) or None
    context = " | ".join(answer.strip() for answer in previous_answers if answer.strip())[:800]
    result = runner.run(
        [
            *base,
            "wizard-question",
            "--domain",
            "setting",
            "--step",
            str(step),
            "--total",
            str(total),
            "--provider",
            provider,
            "--model",
            model,
            "--context",
            context,
        ],
        timeout_seconds=timeout_seconds,
        cwd=cwd,
    )
    if result.ok:
        text = (result.stdout or "").strip().splitlines()
        if text and text[0].strip():
            return text[0].strip()
    return fallback_question


def build_mock_followup(*, step: int, total: int, previous_answers: list[str], fallback: str) -> str:
    latest = ""
    for answer in reversed(previous_answers):
        if answer.strip():
            latest = answer.strip()
            break
    if not latest:
        return fallback
    return f"({step + 1}/{total}) Based on '{latest[:80]}', what concrete detail makes this setting more specific?"
