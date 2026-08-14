"""Additive SQLite schema and version-history migration for documents."""

import sqlite3

from memory.embedding_schema import initialize_embedding_schema


KNOWLEDGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    FOREIGN KEY(document_id) REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    UNIQUE(document_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS knowledge_document_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    chunk_count INTEGER NOT NULL CHECK(chunk_count >= 0),
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(document_id) REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    UNIQUE(document_id, version_number)
);
"""


def initialize_knowledge_schema(connection: sqlite3.Connection) -> None:
    """Create current tables and backfill one version for legacy documents."""
    connection.executescript(KNOWLEDGE_SCHEMA)
    initialize_embedding_schema(connection)
    connection.execute(
        """
        INSERT OR IGNORE INTO knowledge_document_versions (
            document_id, version_number, content_hash, chunk_count, imported_at
        )
        SELECT d.id, 1, d.content_hash, COUNT(c.id), d.imported_at
        FROM knowledge_documents AS d
        LEFT JOIN knowledge_chunks AS c ON c.document_id = d.id
        GROUP BY d.id
        """
    )
