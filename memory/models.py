"""Immutable data-transfer objects for local memory and knowledge."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryEntry:
    """One user-confirmed long-term memory."""

    id: int
    content: str
    category: str
    source: str
    created_at: str


@dataclass(frozen=True)
class KnowledgeDocument:
    """Metadata for one deliberately imported local document."""

    id: int
    source_path: str
    title: str
    content_hash: str
    imported_at: str


@dataclass(frozen=True)
class KnowledgeChunk:
    """One searchable text section belonging to a knowledge document."""

    id: int
    document_id: int
    source_path: str
    title: str
    chunk_index: int
    content: str


@dataclass(frozen=True)
class DocumentImportResult:
    """Outcome of importing or refreshing one controlled document."""

    document: KnowledgeDocument
    chunk_count: int
    changed: bool
