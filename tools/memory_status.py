"""Expose count-only status for confirmed local long-term memory."""

from collections.abc import Callable
from dataclasses import dataclass

from memory.models import MemoryStatistics
from tools.permissions import PermissionLevel
from tools.registry import ToolArguments, ToolDefinition, ToolOutput, ToolRegistry


MAX_MEMORY_ENTRIES = 1_000_000
MemoryStatusReader = Callable[[], MemoryStatistics]


@dataclass(frozen=True)
class LocalMemoryStatusTool:
    """Return aggregate memory counts without stored text or metadata."""

    status_reader: MemoryStatusReader

    @property
    def definition(self) -> ToolDefinition:
        """Beschreibt die argumentlose rein lesende Gedächtnisstatus-Abfrage."""
        return ToolDefinition(
            name="memory.local_status",
            description="Return count-only confirmed local memory status.",
            permission=PermissionLevel.READ_ONLY,
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Liefert begrenzte Zähler, ohne gespeicherte Inhalte offenzulegen."""
        status = self.status_reader()
        _validate_status(status)
        total = status.memories + status.feedback
        return {
            "memories": status.memories,
            "feedback": status.feedback,
            "total_entries": total,
            "spoken_text": _spoken_status(status),
        }


def register_local_memory_status_tool(
    registry: ToolRegistry,
    status_reader: MemoryStatusReader,
) -> None:
    """Registriert einen lokalen Gedächtnisstatus mit reinen Zählerausgaben."""
    registry.register(LocalMemoryStatusTool(status_reader))


def _validate_status(status: MemoryStatistics) -> None:
    """Validiert Gedächtnis- und Feedbackzähler gegen feste Obergrenzen."""
    if not isinstance(status, MemoryStatistics):
        raise TypeError("Memory status reader returned an invalid value.")
    values = (status.memories, status.feedback)
    if not all(type(value) is int for value in values):
        raise TypeError("Memory status counts must be integers.")
    if not all(0 <= value <= MAX_MEMORY_ENTRIES for value in values):
        raise ValueError("Memory status count is outside safe bounds.")
    if sum(values) > MAX_MEMORY_ENTRIES:
        raise ValueError("Total memory status count is outside safe bounds.")


def _spoken_status(status: MemoryStatistics) -> str:
    """Formuliert die lokalen Gedächtniszähler als deutschen Sprechtext."""
    if status.memories == 0 and status.feedback == 0:
        return (
            "Mein lokales Gedächtnis enthält noch keine bestätigten "
            "Erinnerungen oder Stil-Feedbacks."
        )
    memories = _memory_count(status.memories)
    feedback = _feedback_count(status.feedback)
    return f"Mein lokales Gedächtnis enthält {memories} und {feedback}."


def _memory_count(count: int) -> str:
    """Formatiert die Anzahl bestätigter Erinnerungen grammatikalisch korrekt."""
    if count == 1:
        return "eine bestätigte Erinnerung"
    return f"{count} bestätigte Erinnerungen"


def _feedback_count(count: int) -> str:
    """Formatiert die Anzahl bestätigter Stil-Feedbacks grammatikalisch korrekt."""
    if count == 1:
        return "ein bestätigtes Stil-Feedback"
    return f"{count} bestätigte Stil-Feedbacks"
