from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence


@dataclass(frozen=True)
class CommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class Runner(Protocol):
    def run(
        self,
        command: Sequence[str],
        *,
        timeout_seconds: int | None = None,
        cwd: str | Path | None = None,
    ) -> CommandResult:
        ...


class SubprocessCommandRunner:
    def run(
        self,
        command: Sequence[str],
        *,
        timeout_seconds: int | None = None,
        cwd: str | Path | None = None,
    ) -> CommandResult:
        started = time.monotonic()
        try:
            completed = subprocess.run(
                list(command),
                capture_output=True,
                check=False,
                text=True,
                timeout=timeout_seconds,
                cwd=str(cwd) if cwd else None,
            )
            return CommandResult(
                command=tuple(command),
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                command=tuple(command),
                returncode=124,
                stdout=exc.stdout if isinstance(exc.stdout, str) else "",
                stderr=f"Command timed out after {timeout_seconds}s",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        except OSError as exc:
            return CommandResult(
                command=tuple(command),
                returncode=127,
                stdout="",
                stderr=str(exc),
                duration_ms=int((time.monotonic() - started) * 1000),
            )
