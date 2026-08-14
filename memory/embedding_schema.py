"""Additive SQLite schema initialization for local document embeddings."""

import sqlite3


EMBEDDING_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id INTEGER NOT NULL,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    dimension INTEGER NOT NULL CHECK(dimension > 0),
    content_hash TEXT NOT NULL,
    vector BLOB NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(chunk_id)
        REFERENCES knowledge_chunks(id)
        ON DELETE CASCADE,
    UNIQUE(chunk_id, model_name, model_version)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_embeddings_chunk
    ON knowledge_embeddings(chunk_id);
"""


def initialize_embedding_schema(connection: sqlite3.Connection) -> None:
    """Extend an existing knowledge database without destructive migration."""
    connection.executescript(EMBEDDING_SCHEMA)
