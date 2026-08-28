"""Speichert ausdrücklich bestätigte Erinnerungen über die Tool Registry."""

from collections.abc import Callable
from dataclasses import dataclass

from memory.models import MemoryEntry
from tools.permissions import PermissionLevel
from tools.registry import (
    ToolArguments,
    ToolDefinition,
    ToolOutput,
    ToolParameter,
    ToolParameterType,
    ToolRegistry,
)


MAX_MEMORY_CONTENT_LENGTH = 240
MemoryWriter = Callable[..., MemoryEntry]


@dataclass(frozen=True)
class ConfirmedMemoryWriteTool:
    """Schreibt genau eine bestätigte lokale Erinnerung ohne Inhaltsausgabe."""

    writer: MemoryWriter

    @property
    def definition(self) -> ToolDefinition:
        """Beschreibt den bestätigungspflichtigen sensiblen Schreibzugriff."""
        return ToolDefinition(
            name="memory.remember_confirmed",
            description="Store one explicitly confirmed local memory.",
            permission=PermissionLevel.MUTATING,
            parameters=(ToolParameter(
                "content",
                "Explicitly confirmed memory content.",
                ToolParameterType.STRING,
                sensitive=True,
            ),),
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Validiert und speichert den Inhalt, ohne ihn im Ergebnis offenzulegen."""
        content = validate_memory_content(str(arguments["content"]))
        saved = self.writer(
            content,
            category="fact",
            source="user-confirmed-voice",
        )
        if not isinstance(saved, MemoryEntry):
            raise TypeError("Memory writer returned an invalid value.")
        return {
            "stored": True,
            "spoken_text": "Ich habe diese Erinnerung lokal gespeichert.",
        }


def register_confirmed_memory_write_tool(
    registry: ToolRegistry,
    writer: MemoryWriter,
) -> None:
    """Registriert den lokalen Schreibzugriff mit sensibler Inhaltsbehandlung."""
    registry.register(ConfirmedMemoryWriteTool(writer))


def validate_memory_content(content: str) -> str:
    """Begrenzt eine Erinnerung auf einen nichtleeren einzeiligen Sprechtext."""
    normalized = " ".join(content.strip().split())
    if not normalized:
        raise ValueError("Memory content must not be empty.")
    if any(character in content for character in "\r\n\x00"):
        raise ValueError("Memory content must stay on one line.")
    if len(normalized) > MAX_MEMORY_CONTENT_LENGTH:
        raise ValueError("Memory content is too long.")
    return normalized
