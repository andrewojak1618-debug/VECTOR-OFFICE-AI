"""Expose a count-only inventory of the local knowledge library."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from memory.models import DocumentIndexStatus
from tools.permissions import PermissionLevel
from tools.registry import ToolArguments, ToolDefinition, ToolOutput, ToolRegistry


MAX_LIBRARY_ITEMS = 1_000_000
LibraryStatusReader = Callable[[], Iterable[DocumentIndexStatus]]


@dataclass(frozen=True)
class LibraryInventory:
    """Hold bounded aggregate counts without document metadata or content."""

    documents: int
    chunks: int
    current_vectors: int
    stale_vectors: int

    def __post_init__(self) -> None:
        """Validiert alle Bibliothekszähler gegen Typ- und Sicherheitsgrenzen."""
        values = (
            self.documents,
            self.chunks,
            self.current_vectors,
            self.stale_vectors,
        )
        if not all(type(value) is int for value in values):
            raise TypeError("Library inventory counts must be integers.")
        if not all(0 <= value <= MAX_LIBRARY_ITEMS for value in values):
            raise ValueError("Library inventory count is outside safe bounds.")


@dataclass(frozen=True)
class LocalLibraryStatusTool:
    """Return aggregate local library counts through the registry."""

    status_reader: LibraryStatusReader

    @property
    def definition(self) -> ToolDefinition:
        """Beschreibt die argumentlose rein lesende Bibliotheksübersicht."""
        return ToolDefinition(
            name="knowledge.library_status",
            description="Return count-only local knowledge library status.",
            permission=PermissionLevel.READ_ONLY,
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Aggregiert Zustände, ohne identifizierende Dokumentdaten zurückzugeben."""
        inventory = _summarize_statuses(self.status_reader())
        return {
            "documents": inventory.documents,
            "chunks": inventory.chunks,
            "current_vectors": inventory.current_vectors,
            "stale_vectors": inventory.stale_vectors,
            "spoken_text": _spoken_inventory(inventory),
        }


def register_local_library_status_tool(
    registry: ToolRegistry,
    status_reader: LibraryStatusReader,
) -> None:
    """Registriert einen lokalen Bibliotheksstatus mit reinen Zählerausgaben."""
    registry.register(LocalLibraryStatusTool(status_reader))


def _summarize_statuses(
    statuses: Iterable[DocumentIndexStatus],
) -> LibraryInventory:
    """Fasst Dokument- und Vektorstatus zu einer begrenzten Inventur zusammen."""
    items = tuple(statuses)
    if not all(isinstance(status, DocumentIndexStatus) for status in items):
        raise TypeError("Library status reader returned an invalid value.")
    return LibraryInventory(
        len(items),
        sum(status.chunk_count for status in items),
        sum(status.current_vectors for status in items),
        sum(status.stale_vectors for status in items),
    )


def _spoken_inventory(inventory: LibraryInventory) -> str:
    """Erzeugt eine deutsche Sprachausgabe aus den Bibliothekszählern."""
    if inventory.documents == 0:
        return "Die lokale Wissensbibliothek ist leer."
    documents = _count_text(inventory.documents, "Dokument", "Dokumente")
    chunks = _count_text(inventory.chunks, "Abschnitt", "Abschnitten")
    current = _vector_state(inventory.current_vectors, "aktuell")
    stale = _vector_state(inventory.stale_vectors, "veraltet")
    return (
        f"Die lokale Wissensbibliothek enthält {documents} mit {chunks}. "
        f"{current} {stale}"
    )


def _count_text(count: int, singular: str, plural: str) -> str:
    """Verbindet einen Zähler mit der passenden Singular- oder Pluralform."""
    label = singular if count == 1 else plural
    return f"{count} {label}"


def _vector_state(count: int, state: str) -> str:
    """Formuliert Anzahl und Aktualitätszustand gespeicherter Vektoren."""
    subject = _count_text(count, "Vektor", "Vektoren")
    verb = "ist" if count == 1 else "sind"
    return f"{subject} {verb} {state}."
