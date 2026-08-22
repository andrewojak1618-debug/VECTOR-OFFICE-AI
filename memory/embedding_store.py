"""Compact, version-aware SQLite persistence for document embeddings."""

import hashlib
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Sequence

from memory.embedding_records import (
    ChunkEmbedding,
    EmbeddedKnowledgeChunk,
    Float32VectorCodec,
    StoredEmbedding,
)
from memory.embedding_schema import initialize_embedding_schema
from memory.embeddings import (
    EmbeddingModelInfo,
    EmbeddingResult,
)
from memory.models import KnowledgeChunk


class SQLiteEmbeddingStore:
    """Persist generated document vectors with model and content provenance."""

    def __init__(self, database_path: str | Path):
        """Initialisiert die lokale SQLite-Ablage für versionierte Vektoren."""
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Öffnet eine transaktionale Verbindung mit aktiven Fremdschlüsseln."""
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        """Erweitert die Datenbank sicher um das Einbettungsschema."""
        with self._connect() as connection:
            initialize_embedding_schema(connection)

    def save(
        self,
        embedding: ChunkEmbedding,
        model: EmbeddingModelInfo,
    ) -> StoredEmbedding:
        """Speichert eine Abschnittseinbettung und liefert ihre Datenbankdarstellung."""
        return self.save_many((embedding,), model)[0]

    def save_many(
        self,
        embeddings: Sequence[ChunkEmbedding],
        model: EmbeddingModelInfo,
    ) -> tuple[StoredEmbedding, ...]:
        """Speichert einen geordneten Stapel atomar ohne doppelte Identitäten."""
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
        """Liefert gespeicherte Vektoren nach ihrem Quelldokumentabschnitt geordnet."""
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
        """Liefert Vektoren, die nicht mehr zu Inhalt oder Modellidentität passen."""
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
        """Liefert Abschnittskennungen ohne aktuelle Einbettung für das Modell."""
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
        """Meldet Vektoren eines Dokuments mit abweichender Modellidentität."""
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
        """Liefert alle Abschnitte mit gültiger Einbettung einer Modellidentität."""
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
        """Validiert und speichert eine Einbettung unter ihrer eindeutigen Identität."""
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
        """Liefert die feste SQL-Anweisung für kollisionsfreie Aktualisierungen."""
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
        """Erzeugt die serialisierten Werte für eine Einbettungszeile."""
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
        """Liest den Quelltext eines vorhandenen Dokumentabschnitts."""
        row = connection.execute(
            "SELECT content FROM knowledge_chunks WHERE id = ?",
            (chunk_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Embedding source chunk does not exist.")
        return row["content"]

    @staticmethod
    def _validate_embedding_content(content: str, result: EmbeddingResult) -> None:
        """Verhindert die Zuordnung eines Vektors zu abweichendem Quelltext."""
        if content != result.text.value:
            raise ValueError("Embedding text does not match its source chunk.")

    @staticmethod
    def _validate_result_dimension(
        result: EmbeddingResult,
        model: EmbeddingModelInfo,
    ) -> None:
        """Prüft die Ergebnisdimension gegen die bekannte Modellmetadimension."""
        if result.dimension != model.dimension:
            raise ValueError("Embedding dimension does not match model metadata.")

    @staticmethod
    def _validate_model(model: EmbeddingModelInfo) -> None:
        """Verlangt eine vollständige lokale Modellidentität samt Dimension."""
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
        """Liest die Datenbankkennung einer eindeutigen Abschnitt-Modell-Kombination."""
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
        """Liest eine gespeicherte Einbettung anhand ihrer Kennung."""
        return connection.execute(
            "SELECT * FROM knowledge_embeddings WHERE id = ?",
            (embedding_id,),
        ).fetchone()

    @staticmethod
    def _content_hash(content: str) -> str:
        """Berechnet die stabile SHA-256-Prüfsumme eines Abschnittstextes."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @classmethod
    def _is_current_row(
        cls,
        row: sqlite3.Row,
        model: EmbeddingModelInfo,
    ) -> bool:
        """Prüft Modell, Dimension und Inhalt einer gespeicherten Zeile auf Aktualität."""
        return (
            row["model_name"] == model.model_name
            and row["model_version"] == model.model_version
            and row["dimension"] == model.dimension
            and row["content_hash"] == cls._content_hash(row["current_content"])
        )

    @staticmethod
    def _to_stored(row: sqlite3.Row) -> StoredEmbedding:
        """Überführt eine SQLite-Zeile in eine validierte gespeicherte Einbettung."""
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
        """Verbindet einen belegten Wissensabschnitt mit seinem dekodierten Vektor."""
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
