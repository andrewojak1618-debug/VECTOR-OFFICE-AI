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
class KnowledgeDocumentVersion:
    """One immutable metadata revision of an imported document."""

    id: int
    document_id: int
    version_number: int
    content_hash: str
    chunk_count: int
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


@dataclass(frozen=True)
class IndexingResult:
    """Summarize one incremental or forced document indexing run."""

    document_id: int
    total_chunks: int
    indexed_chunks: int
    skipped_chunks: int
    model_changed: bool
    forced: bool


@dataclass(frozen=True)
class DocumentIndexStatus:
    """Summarize current and stale vectors for one document."""

    document: KnowledgeDocument
    version_count: int
    chunk_count: int
    model_name: str
    model_version: str
    dimension: int | None
    current_vectors: int
    stale_vectors: int


@dataclass(frozen=True)
class StaleEmbeddingStatus:
    """Identify stale vector metadata without exposing vector values."""

    document_id: int
    chunk_id: int
    model_name: str
    model_version: str
    dimension: int
    updated_at: str
