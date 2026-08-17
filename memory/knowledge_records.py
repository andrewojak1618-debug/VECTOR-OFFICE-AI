"""Map knowledge rows and rank lexical document candidates."""

import re
import sqlite3

from memory.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
)


DEFAULT_TERM_MIN_LENGTH = 4


def search_terms(
    query: str,
    minimum_length: int = DEFAULT_TERM_MIN_LENGTH,
) -> frozenset[str]:
    """Return normalized lexical terms above one minimum length."""
    return frozenset(
        term
        for term in re.findall(r"\w+", query.casefold())
        if len(term) >= minimum_length
    )


def rank_chunk_rows(
    rows: tuple[sqlite3.Row, ...],
    terms: frozenset[str],
    limit: int,
) -> tuple[KnowledgeChunk, ...]:
    """Rank document rows by lexical overlap and newest row identity."""
    scored = []
    for row in rows:
        text = f"{row['title']} {row['content']}".casefold()
        score = sum(term in text for term in terms)
        if score:
            scored.append((score, row["id"], to_chunk(row)))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return tuple(item[2] for item in scored[:limit])


def to_document(row: sqlite3.Row) -> KnowledgeDocument:
    """Map one SQLite row to immutable document metadata."""
    return KnowledgeDocument(
        id=row["id"],
        source_path=row["source_path"],
        title=row["title"],
        content_hash=row["content_hash"],
        imported_at=row["imported_at"],
    )


def to_chunk(row: sqlite3.Row) -> KnowledgeChunk:
    """Map one joined SQLite row to a sourced knowledge chunk."""
    return KnowledgeChunk(
        id=row["id"],
        document_id=row["document_id"],
        source_path=row["source_path"],
        title=row["title"],
        chunk_index=row["chunk_index"],
        content=row["content"],
    )


def to_document_version(row: sqlite3.Row) -> KnowledgeDocumentVersion:
    """Map one SQLite row to immutable document-version metadata."""
    return KnowledgeDocumentVersion(
        id=row["id"],
        document_id=row["document_id"],
        version_number=row["version_number"],
        content_hash=row["content_hash"],
        chunk_count=row["chunk_count"],
        imported_at=row["imported_at"],
    )
