from __future__ import annotations

from collections.abc import Sequence

from world_muse.adapters import agent_foundry
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
        provider="custom-provider",
        model="gpt-4.1",
    )

    assert result.ok is True
    assert len(runner.calls) == 1
    assert runner.calls[0][-5:] == (
        "test-llm-connection",
        "--provider",
        "custom-provider",
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


def test_test_llm_connection_mock_provider_short_circuits_external_call():
    settings = AppSettings()
    runner = FakeRunner(returncode=1, stderr="should not be called")

    result = run_llm_connection_test(
        settings=settings,
        runner=runner,
        provider="mock",
        model="mock-world-muse-v1",
    )

    assert result.ok is True
    assert runner.calls == []
    assert "Mock provider selected" in result.result.stdout


def test_test_llm_connection_openai_uses_direct_check_without_runner(monkeypatch):
    settings = AppSettings()
    settings.agent_foundry_executable = "agentfoundry"
    settings.agent_foundry_working_directory = ""
    runner = FakeRunner(returncode=1, stderr="should not be called")

    def fake_direct_test(*, model: str, timeout_seconds: int) -> CommandResult:
        assert model == "gpt-4.1"
        assert timeout_seconds == 60
        return CommandResult(
            command=("openai", "models.retrieve", model),
            returncode=0,
            stdout="OpenAI connection OK",
            stderr="",
            duration_ms=1,
        )

    monkeypatch.setattr(agent_foundry, "run_direct_openai_connection_test", fake_direct_test)
    result = run_llm_connection_test(
        settings=settings,
        runner=runner,
        provider="openai",
        model="gpt-4.1",
    )

    assert result.ok is True
    assert len(runner.calls) == 0
    assert result.result.command[:2] == ("openai", "models.retrieve")


def test_run_direct_openai_connection_test_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = agent_foundry.run_direct_openai_connection_test(model="gpt-4.1", timeout_seconds=5)
    assert result.ok is False
    assert "OPENAI_API_KEY is not set" in result.stderr


def test_generate_styled_description_requires_summary():
    result = agent_foundry.generate_styled_description(
        provider="mock",
        model="mock-world-muse-v1",
        style="Dramatic",
        summary="",
        existing_description="",
    )
    assert result.ok is False
    assert "Summary is required" in result.error


def test_generate_styled_description_mock_generate_and_rewrite():
    generated = agent_foundry.generate_styled_description(
        provider="mock",
        model="mock-world-muse-v1",
        style="Comedic",
        summary="A floating bazaar above acid clouds.",
        existing_description="",
    )
    rewritten = agent_foundry.generate_styled_description(
        provider="mock",
        model="mock-world-muse-v1",
        style="Urgent",
        summary="A floating bazaar above acid clouds.",
        existing_description="The market drifts and sings.",
    )
    assert generated.ok is True
    assert "[Comedic]" in generated.text
    assert rewritten.ok is True
    assert "refined from summary" in rewritten.text


def test_build_description_messages_switches_modes():
    fresh = agent_foundry.build_description_messages(
        style="Suspenseful",
        summary="Hidden tunnels beneath the cathedral.",
        existing_description="",
    )
    rewrite = agent_foundry.build_description_messages(
        style="Suspenseful",
        summary="Hidden tunnels beneath the cathedral.",
        existing_description="The tunnels are old and damp.",
    )
    assert "Write a fresh description" in fresh[1]["content"]
    assert "Rewrite the existing description" in rewrite[1]["content"]
