"""Definiert die providerunabhängigen Verträge des Gesprächsagenten."""

from pathlib import Path
from typing import Protocol, Sequence

from brain.context import ChatMessage
from memory.models import (
    DocumentImportResult,
    DocumentIndexStatus,
    IndexingResult,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    MemoryEntry,
    StaleEmbeddingStatus,
)


class LanguageModel(Protocol):
    """Beschreibt die gemeinsame Schnittstelle aller Sprachmodelle."""

    def generate(self, messages: Sequence[ChatMessage]) -> str:
        """Erzeugt eine Assistentenantwort für den übergebenen Gesprächsverlauf."""
        ...


class MemoryStore(Protocol):
    """Beschreibt kontrolliertes Speichern und Suchen bestätigter Erinnerungen."""

    def search(self, query: str, limit: int = 5) -> Sequence[MemoryEntry]:
        """Liefert zur Anfrage passende bestätigte Erinnerungen."""
        ...

    def remember(
        self,
        content: str,
        category: str = "fact",
        source: str = "user-confirmed",
    ) -> MemoryEntry:
        """Speichert eine ausdrücklich bestätigte Erinnerung dauerhaft."""
        ...

    def list_memories(self, limit: int = 20) -> Sequence[MemoryEntry]:
        """Liefert zuletzt bestätigte Erinnerungen."""
        ...

    def list_feedback(self, limit: int = 5) -> Sequence[MemoryEntry]:
        """Liefert ausdrücklich bestätigtes Kommunikationsfeedback."""
        ...

    def forget(self, memory_id: int) -> bool:
        """Löscht eine Erinnerung anhand ihrer Kennung."""
        ...

    def export_confirmed_memories(self, destination: str) -> Path:
        """Exportiert bestätigte Erinnerungen in eine bereinigte lokale JSON-Datei."""
        ...


class KnowledgeLibrary(Protocol):
    """Beschreibt kontrollierte Verwaltung und Suche lokaler Dokumente."""

    def search(self, query: str, limit: int = 5) -> Sequence[KnowledgeChunk]:
        """Liefert zur Anfrage passende Abschnitte importierter Dokumente."""
        ...

    def import_document(self, source_path: str) -> DocumentImportResult:
        """Importiert oder aktualisiert ein bewusst ausgewähltes Dokument."""
        ...

    def list_documents(self, limit: int = 50) -> Sequence[KnowledgeDocument]:
        """Liefert Metadaten importierter Dokumente."""
        ...

    def forget_document(self, document_id: int) -> bool:
        """Löscht ein importiertes Dokument samt Abschnitten."""
        ...

    def reindex_document(self, document_id: int) -> IndexingResult:
        """Erzwingt einen neuen lokalen semantischen Index für ein Dokument."""
        ...

    def reindex_all(self) -> Sequence[IndexingResult]:
        """Erzwingt einen neuen lokalen semantischen Index für alle Dokumente."""
        ...

    def list_document_statuses(self) -> Sequence[DocumentIndexStatus]:
        """Liefert Dokument-, Versions-, Modell- und Vektormetadaten."""
        ...

    def list_document_versions(
        self,
        document_id: int,
    ) -> Sequence[KnowledgeDocumentVersion]:
        """Liefert den Metadatenverlauf eines Dokuments."""
        ...

    def list_stale_vectors(self) -> Sequence[StaleEmbeddingStatus]:
        """Liefert Metadaten veralteter Vektoren ohne deren Zahlenwerte."""
        ...

    def export_library_metadata(self, destination: str) -> Path:
        """Exportiert bereinigte Bibliotheksmetadaten in lokales JSON."""
        ...
