from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request

from ..command_runner import CommandResult, Runner
from ..config import AppSettings


@dataclass(frozen=True)
class AgentFoundryConnectionResult:
    result: CommandResult
    executable: str

    @property
    def ok(self) -> bool:
        return self.result.ok


def mock_success_result(command: list[str], message: str) -> CommandResult:
    return CommandResult(
        command=tuple(command),
        returncode=0,
        stdout=message,
        stderr="",
        duration_ms=1,
    )


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
    if provider == "mock":
        result = mock_success_result(
            ["mock", "test-llm-connection", "--provider", provider, "--model", model],
            "Mock provider selected; connection check skipped.",
        )
        return AgentFoundryConnectionResult(result=result, executable="mock")
    if provider == "openai":
        result = run_direct_openai_connection_test(model=model, timeout_seconds=timeout_seconds)
        return AgentFoundryConnectionResult(result=result, executable="openai-http")

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
    if (not result.ok) and ("No module named typer" in result.stderr):
        hint = "Install deps for Python 3.11: python3.11 -m pip install typer rich httpx pyyaml pydantic"
        result = CommandResult(
            command=result.command,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=f"{result.stderr.strip()} | {hint}",
            duration_ms=result.duration_ms,
        )
    return AgentFoundryConnectionResult(result=result, executable=" ".join(base))


def run_direct_openai_connection_test(*, model: str, timeout_seconds: int) -> CommandResult:
    command = ("openai", "models.retrieve", model)
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return CommandResult(
            command=command,
            returncode=2,
            stdout="",
            stderr="OPENAI_API_KEY is not set",
            duration_ms=1,
        )

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    url = f"{base_url}/models/{model}"
    req = request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")
            return CommandResult(
                command=command,
                returncode=0,
                stdout=f"OpenAI connection OK ({response.status}) {body[:500]}",
                stderr="",
                duration_ms=1,
            )
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(detail)
            message = str(payload.get("error", {}).get("message") or detail)
        except json.JSONDecodeError:
            message = detail
        return CommandResult(
            command=command,
            returncode=exc.code,
            stdout="",
            stderr=f"OpenAI HTTP {exc.code}: {message[:500]}",
            duration_ms=1,
        )
    except Exception as exc:  # pragma: no cover - safety net for local networking/runtime issues
        return CommandResult(
            command=command,
            returncode=1,
            stdout="",
            stderr=f"OpenAI connection failed: {exc}",
            duration_ms=1,
        )


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
