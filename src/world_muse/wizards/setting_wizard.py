from __future__ import annotations

from dataclasses import dataclass, field

SETTING_QUESTIONS = [
    "What is the name of your setting, and what feeling should it evoke?",
    "What is one defining place in this world that people would instantly recognize?",
    "What rule, law, or natural force shapes everyday life in this setting?",
    "What major tension or conflict is currently reshaping this world?",
    "Who is most affected by that tension, and what do they stand to lose?",
]


@dataclass
class SettingWizardSession:
    questions: list[str] = field(default_factory=lambda: list(SETTING_QUESTIONS))
    index: int = 0
    answers: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.answers:
            self.answers = [""] * len(self.questions)
        elif len(self.answers) < len(self.questions):
            self.answers.extend([""] * (len(self.questions) - len(self.answers)))
        elif len(self.answers) > len(self.questions):
            self.answers = self.answers[: len(self.questions)]

    @property
    def total(self) -> int:
        return len(self.questions)

    @property
    def is_first(self) -> bool:
        return self.index <= 0

    @property
    def is_last(self) -> bool:
        return self.index >= self.total - 1

    @property
    def current_question(self) -> str:
        return self.questions[self.index]

    @property
    def current_answer(self) -> str:
        return self.answers[self.index]

    def set_current_answer(self, value: str) -> None:
        self.answers[self.index] = value

    def prev(self) -> None:
        if not self.is_first:
            self.index -= 1

    def next(self) -> None:
        if not self.is_last:
            self.index += 1

    def as_detail_map(self) -> dict[str, str]:
        return {f"Q{i + 1}: {question}": self.answers[i].strip() for i, question in enumerate(self.questions)}

    def build_summary(self) -> str:
        non_empty = [answer.strip() for answer in self.answers if answer.strip()]
        if not non_empty:
            return "No setting details captured yet."
        return non_empty[0]
