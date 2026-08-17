"""Bounded in-memory context for one conversation session."""

from dataclasses import dataclass, field
from typing import Literal

from brain.personality import DEFAULT_SYSTEM_PROMPT


MessageRole = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class ChatMessage:
    """One normalized message sent to a language model."""

    role: MessageRole
    content: str


@dataclass(frozen=True)
class ConversationCheckpoint:
    """Capture one restorable in-memory history snapshot."""

    history: tuple[ChatMessage, ...]


@dataclass
class ConversationContext:
    """Store a bounded user/assistant history with one system prompt."""

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
        """Return an immutable snapshot without the system prompt."""
        return tuple(self._history)

    def add_user_message(self, content: str) -> None:
        """Append one validated user message."""
        self._add_message("user", content)

    def add_assistant_message(self, content: str) -> None:
        """Append one validated assistant message."""
        self._add_message("assistant", content)

    def messages(self) -> tuple[ChatMessage, ...]:
        """Return the complete model-ready message sequence."""
        return (
            ChatMessage(role="system", content=self.system_prompt),
            *self._history,
        )

    def checkpoint(self) -> ConversationCheckpoint:
        """Capture the current bounded history for a tentative response."""
        return ConversationCheckpoint(tuple(self._history))

    def restore(self, checkpoint: ConversationCheckpoint) -> None:
        """Restore one validated snapshot without changing configuration."""
        if not isinstance(checkpoint, ConversationCheckpoint):
            raise TypeError("Context restore requires a checkpoint.")
        history = checkpoint.history
        if len(history) > self.max_history_messages:
            raise ValueError("Checkpoint exceeds the context history limit.")
        if not all(isinstance(message, ChatMessage) for message in history):
            raise TypeError("Checkpoint contains an invalid message.")
        if history and history[0].role == "assistant":
            raise ValueError("Checkpoint must not start with an assistant message.")
        self._history = list(history)

    def clear(self) -> None:
        """Clear conversational history while preserving configuration."""
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
