from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class StatusMessage:
    level: str
    text: str
    timestamp: datetime


@dataclass
class StatusLog:
    messages: list[StatusMessage] = field(default_factory=list)

    def add(self, level: str, text: str) -> None:
        self.messages.append(StatusMessage(level=level, text=text, timestamp=datetime.now()))

    def info(self, text: str) -> None:
        self.add("info", text)

    def warning(self, text: str) -> None:
        self.add("warning", text)

    def error(self, text: str) -> None:
        self.add("error", text)
