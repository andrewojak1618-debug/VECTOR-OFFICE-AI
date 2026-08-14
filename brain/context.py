from dataclasses import dataclass, field
from typing import Literal

from brain.personality import DEFAULT_SYSTEM_PROMPT


MessageRole = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class ChatMessage:
    role: MessageRole
    content: str


@dataclass
class ConversationContext:
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    max_history_messages: int = 20
    _history: list[ChatMessage] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.system_prompt.strip():
            raise ValueError("System prompt must not be empty.")

        if self.max_history_messages < 1:
            raise ValueError("max_history_messages must be at least 1.")

    @property
    def history(self) -> tuple[ChatMessage, ...]:
        return tuple(self._history)

    def add_user_message(self, content: str) -> None:
        self._add_message("user", content)

    def add_assistant_message(self, content: str) -> None:
        self._add_message("assistant", content)

    def messages(self) -> tuple[ChatMessage, ...]:
        return (
            ChatMessage(role="system", content=self.system_prompt),
            *self._history,
        )

    def clear(self) -> None:
        self._history.clear()

    def _add_message(self, role: MessageRole, content: str) -> None:
        normalized_content = content.strip()

        if not normalized_content:
            raise ValueError("Conversation messages must not be empty.")

        self._history.append(
            ChatMessage(role=role, content=normalized_content)
        )

        if len(self._history) > self.max_history_messages:
            self._history = self._history[-self.max_history_messages :]

        while self._history and self._history[0].role == "assistant":
            self._history.pop(0)
