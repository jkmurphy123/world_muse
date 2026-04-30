from __future__ import annotations

from collections.abc import Sequence

from world_muse.adapters.agent_foundry import generate_setting_question, run_llm_connection_test
from world_muse.command_runner import CommandResult
from world_muse.config import AppSettings


class FakeRunner:
    def __init__(self, *, returncode: int = 0, stdout: str = "ok", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.calls: list[tuple[str, ...]] = []

    def run(self, command: Sequence[str], *, timeout_seconds: int | None = None, cwd=None) -> CommandResult:
        self.calls.append(tuple(command))
        return CommandResult(
            command=tuple(command),
            returncode=self.returncode,
            stdout=self.stdout,
            stderr=self.stderr,
            duration_ms=1,
        )


def test_test_llm_connection_builds_expected_command():
    settings = AppSettings()
    settings.agent_foundry_executable = "agentfoundry"
    settings.agent_foundry_working_directory = ""
    runner = FakeRunner(returncode=0)

    result = run_llm_connection_test(
        settings=settings,
        runner=runner,
        provider="openai",
        model="gpt-4.1",
    )

    assert result.ok is True
    assert len(runner.calls) == 1
    assert runner.calls[0][-5:] == (
        "test-llm-connection",
        "--provider",
        "openai",
        "--model",
        "gpt-4.1",
    )


def test_generate_setting_question_falls_back_on_failure():
    settings = AppSettings()
    settings.agent_foundry_executable = "agentfoundry"
    settings.agent_foundry_working_directory = ""
    runner = FakeRunner(returncode=1, stderr="boom")

    question = generate_setting_question(
        settings=settings,
        runner=runner,
        provider="openai",
        model="gpt-4.1",
        step=2,
        total=5,
        previous_answers=["A city above storms"],
        fallback_question="What rule controls this place?",
    )

    assert question == "What rule controls this place?"


def test_generate_setting_question_uses_mock_strategy():
    settings = AppSettings()
    runner = FakeRunner(returncode=0)

    question = generate_setting_question(
        settings=settings,
        runner=runner,
        provider="mock",
        model="mock-world-muse-v1",
        step=2,
        total=5,
        previous_answers=["A city above storms"],
        fallback_question="What rule controls this place?",
    )

    assert "A city above storms" in question
