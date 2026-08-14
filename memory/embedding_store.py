"""Compact, version-aware SQLite persistence for document embeddings."""

import hashlib
import sqlite3
import struct
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

from memory.embedding_schema import initialize_embedding_schema
from memory.embeddings import (
    EmbeddingModelInfo,
    EmbeddingResult,
    EmbeddingVector,
)
from memory.models import KnowledgeChunk


@dataclass(frozen=True)
class ChunkEmbedding:
    """Associate one generated embedding with its source chunk identifier."""

    chunk_id: int
    result: EmbeddingResult


@dataclass(frozen=True)
class StoredEmbedding:
    """Represent one versioned embedding restored from local SQLite."""

    id: int
    chunk_id: int
    model_name: str
    model_version: str
    dimension: int
    content_hash: str
    vector: EmbeddingVector
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class EmbeddedKnowledgeChunk:
    """Pair a sourced document section with its current local vector."""

    chunk: KnowledgeChunk
    vector: EmbeddingVector


class Float32VectorCodec:
    """Serialize numeric vectors as compact little-endian float32 blobs."""

    BYTES_PER_VALUE = 4

    @classmethod
    def encode(cls, vector: EmbeddingVector) -> bytes:
        """Encode one validated vector into a compact SQLite BLOB."""
        try:
            return struct.pack(f"<{vector.dimension}f", *vector.values)
        except (OverflowError, struct.error) as exc:
            raise ValueError("Embedding vector cannot be encoded as float32.") from exc

    @classmethod
    def decode(cls, payload: bytes, dimension: int) -> EmbeddingVector:
        """Decode a BLOB and verify its stored vector dimension."""
        expected_bytes = dimension * cls.BYTES_PER_VALUE
        if dimension < 1 or len(payload) != expected_bytes:
            raise ValueError("Stored embedding vector has an invalid size.")
        values = struct.unpack(f"<{dimension}f", payload)
        return EmbeddingVector(values)


class SQLiteEmbeddingStore:
    """Persist generated document vectors with model and content provenance."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            initialize_embedding_schema(connection)

    def save(
        self,
        embedding: ChunkEmbedding,
        model: EmbeddingModelInfo,
    ) -> StoredEmbedding:
        """Upsert one chunk embedding and return its stored representation."""
        return self.save_many((embedding,), model)[0]

    def save_many(
        self,
        embeddings: Sequence[ChunkEmbedding],
        model: EmbeddingModelInfo,
    ) -> tuple[StoredEmbedding, ...]:
        """Atomically persist an ordered batch without duplicate identities."""
        batch = tuple(embeddings)
        if not batch:
            return ()
        self._validate_model(model)
        with self._connect() as connection:
            stored_ids = tuple(
                self._upsert(connection, embedding, model)
                for embedding in batch
            )
            rows = tuple(
                self._find_by_id(connection, embedding_id)
                for embedding_id in stored_ids
            )
        return tuple(self._to_stored(row) for row in rows)

    def list_for_document(self, document_id: int) -> tuple[StoredEmbedding, ...]:
        """Return stored vectors ordered by their source document section."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT e.*
                FROM knowledge_embeddings AS e
                JOIN knowledge_chunks AS c ON c.id = e.chunk_id
                WHERE c.document_id = ?
                ORDER BY c.chunk_index, e.id
                """,
                (document_id,),
            ).fetchall()
        return tuple(self._to_stored(row) for row in rows)

    def list_stale_for_document(
        self,
        document_id: int,
        model: EmbeddingModelInfo,
    ) -> tuple[StoredEmbedding, ...]:
        """Return vectors that no longer match content or current model identity."""
        self._validate_model(model)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT e.*, c.content AS current_content
                FROM knowledge_embeddings AS e
                JOIN knowledge_chunks AS c ON c.id = e.chunk_id
                WHERE c.document_id = ?
                ORDER BY c.chunk_index, e.id
                """,
                (document_id,),
            ).fetchall()
        stale = (row for row in rows if not self._is_current_row(row, model))
        return tuple(self._to_stored(row) for row in stale)

    def pending_chunk_ids(
        self,
        document_id: int,
        model: EmbeddingModelInfo,
    ) -> tuple[int, ...]:
        """Return chunk IDs without a current embedding for ``model``."""
        self._validate_model(model)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT c.id, c.content, e.dimension, e.content_hash
                FROM knowledge_chunks AS c
                LEFT JOIN knowledge_embeddings AS e
                    ON e.chunk_id = c.id
                    AND e.model_name = ?
                    AND e.model_version = ?
                WHERE c.document_id = ?
                ORDER BY c.chunk_index
                """,
                (model.model_name, model.model_version, document_id),
            ).fetchall()
        return tuple(
            row["id"]
            for row in rows
            if row["dimension"] is None
            or row["dimension"] != model.dimension
            or row["content_hash"] != self._content_hash(row["content"])
        )

    def has_other_model_identity(
        self,
        document_id: int,
        model: EmbeddingModelInfo,
    ) -> bool:
        """Report whether a document has vectors from another model identity."""
        self._validate_model(model)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM knowledge_embeddings AS e
                JOIN knowledge_chunks AS c ON c.id = e.chunk_id
                WHERE c.document_id = ?
                  AND (e.model_name != ? OR e.model_version != ?)
                LIMIT 1
                """,
                (document_id, model.model_name, model.model_version),
            ).fetchone()
        return row is not None

    def list_current_chunks(
        self,
        model: EmbeddingModelInfo,
    ) -> tuple[EmbeddedKnowledgeChunk, ...]:
        """Return all sections with a valid embedding for one model identity."""
        self._validate_model(model)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT e.vector, e.dimension, e.content_hash,
                       c.id AS chunk_id, c.document_id, c.chunk_index,
                       c.content, d.source_path, d.title
                FROM knowledge_embeddings AS e
                JOIN knowledge_chunks AS c ON c.id = e.chunk_id
                JOIN knowledge_documents AS d ON d.id = c.document_id
                WHERE e.model_name = ? AND e.model_version = ?
                  AND e.dimension = ?
                ORDER BY d.id, c.chunk_index
                """,
                (model.model_name, model.model_version, model.dimension),
            ).fetchall()
        current = (
            row for row in rows
            if row["content_hash"] == self._content_hash(row["content"])
        )
        return tuple(self._to_embedded_chunk(row) for row in current)

    def _upsert(
        self,
        connection: sqlite3.Connection,
        embedding: ChunkEmbedding,
        model: EmbeddingModelInfo,
    ) -> int:
        content = self._chunk_content(connection, embedding.chunk_id)
        self._validate_embedding_content(content, embedding.result)
        self._validate_result_dimension(embedding.result, model)
        connection.execute(
            self._upsert_sql(),
            self._upsert_values(embedding, model, content),
        )
        return self._find_identity_id(connection, embedding.chunk_id, model)

    @staticmethod
    def _upsert_sql() -> str:
        return """
            INSERT INTO knowledge_embeddings (
                chunk_id, model_name, model_version, dimension,
                content_hash, vector
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(chunk_id, model_name, model_version) DO UPDATE SET
                dimension = excluded.dimension,
                content_hash = excluded.content_hash,
                vector = excluded.vector,
                updated_at = CURRENT_TIMESTAMP
        """

    @staticmethod
    def _upsert_values(
        embedding: ChunkEmbedding,
        model: EmbeddingModelInfo,
        content: str,
    ) -> tuple:
        return (
            embedding.chunk_id,
            model.model_name,
            model.model_version,
            embedding.result.dimension,
            SQLiteEmbeddingStore._content_hash(content),
            Float32VectorCodec.encode(embedding.result.vector),
        )

    @staticmethod
    def _chunk_content(connection: sqlite3.Connection, chunk_id: int) -> str:
        row = connection.execute(
            "SELECT content FROM knowledge_chunks WHERE id = ?",
            (chunk_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Embedding source chunk does not exist.")
        return row["content"]

    @staticmethod
    def _validate_embedding_content(content: str, result: EmbeddingResult) -> None:
        if content != result.text.value:
            raise ValueError("Embedding text does not match its source chunk.")

    @staticmethod
    def _validate_result_dimension(
        result: EmbeddingResult,
        model: EmbeddingModelInfo,
    ) -> None:
        if result.dimension != model.dimension:
            raise ValueError("Embedding dimension does not match model metadata.")

    @staticmethod
    def _validate_model(model: EmbeddingModelInfo) -> None:
        if not model.model_name.strip() or not model.model_version.strip():
            raise ValueError("Embedding model identity must not be empty.")
        if model.dimension is None or model.dimension < 1:
            raise ValueError("Embedding model dimension must be known.")

    @staticmethod
    def _find_identity_id(
        connection: sqlite3.Connection,
        chunk_id: int,
        model: EmbeddingModelInfo,
    ) -> int:
        row = connection.execute(
            """
            SELECT id FROM knowledge_embeddings
            WHERE chunk_id = ? AND model_name = ? AND model_version = ?
            """,
            (chunk_id, model.model_name, model.model_version),
        ).fetchone()
        return row["id"]

    @staticmethod
    def _find_by_id(
        connection: sqlite3.Connection,
        embedding_id: int,
    ) -> sqlite3.Row:
        return connection.execute(
            "SELECT * FROM knowledge_embeddings WHERE id = ?",
            (embedding_id,),
        ).fetchone()

    @staticmethod
    def _content_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @classmethod
    def _is_current_row(
        cls,
        row: sqlite3.Row,
        model: EmbeddingModelInfo,
    ) -> bool:
        return (
            row["model_name"] == model.model_name
            and row["model_version"] == model.model_version
            and row["dimension"] == model.dimension
            and row["content_hash"] == cls._content_hash(row["current_content"])
        )

    @staticmethod
    def _to_stored(row: sqlite3.Row) -> StoredEmbedding:
        return StoredEmbedding(
            id=row["id"],
            chunk_id=row["chunk_id"],
            model_name=row["model_name"],
            model_version=row["model_version"],
            dimension=row["dimension"],
            content_hash=row["content_hash"],
            vector=Float32VectorCodec.decode(row["vector"], row["dimension"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _to_embedded_chunk(row: sqlite3.Row) -> EmbeddedKnowledgeChunk:
        chunk = KnowledgeChunk(
            id=row["chunk_id"],
            document_id=row["document_id"],
            source_path=row["source_path"],
            title=row["title"],
            chunk_index=row["chunk_index"],
            content=row["content"],
        )
        vector = Float32VectorCodec.decode(row["vector"], row["dimension"])
        return EmbeddedKnowledgeChunk(chunk, vector)
