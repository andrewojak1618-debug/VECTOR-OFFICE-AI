from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryEntry:
    id: int
    content: str
    category: str
    source: str
    created_at: str


@dataclass(frozen=True)
class KnowledgeDocument:
    id: int
    source_path: str
    title: str
    content_hash: str
    imported_at: str


@dataclass(frozen=True)
class KnowledgeChunk:
    id: int
    document_id: int
    source_path: str
    title: str
    chunk_index: int
    content: str


@dataclass(frozen=True)
class DocumentImportResult:
    document: KnowledgeDocument
    chunk_count: int
    changed: bool
