"""Control local document imports and SQLite knowledge storage."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from memory.document_text import DocumentTextProcessor, PreparedDocument
from memory.knowledge_records import (
    DEFAULT_TERM_MIN_LENGTH,
    rank_chunk_rows,
    search_terms,
    to_chunk,
    to_document,
    to_document_version,
)
from memory.knowledge_schema import initialize_knowledge_schema
from memory.models import (
    DocumentImportResult,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
)


class SQLiteKnowledgeLibrary:
    """Store explicitly imported documents in a local SQLite database."""

    ALLOWED_EXTENSIONS = DocumentTextProcessor.ALLOWED_EXTENSIONS
    DEFAULT_MAX_FILE_BYTES = DocumentTextProcessor.DEFAULT_MAX_FILE_BYTES
    DEFAULT_CHUNK_SIZE = DocumentTextProcessor.DEFAULT_CHUNK_SIZE
    MIN_CHUNK_SIZE = DocumentTextProcessor.MIN_CHUNK_SIZE
    TERM_MIN_LENGTH = DEFAULT_TERM_MIN_LENGTH

    def __init__(
        self,
        database_path: str | Path,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ):
        """Initialisiert die lokale Bibliothek mit validierter Textverarbeitung."""
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_file_bytes = max_file_bytes
        self.chunk_size = chunk_size
        self.text_processor = DocumentTextProcessor(max_file_bytes, chunk_size)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Öffnet eine transaktionale SQLite-Verbindung mit Fremdschlüsseln."""
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        """Legt das aktuelle additive Wissens- und Einbettungsschema an."""
        with self._connect() as connection:
            initialize_knowledge_schema(connection)

    def import_document(self, source_path: str | Path) -> DocumentImportResult:
        """Importiert oder aktualisiert ein freigegebenes UTF-8-Dokument atomar."""
        prepared = self.text_processor.prepare(source_path)
        with self._connect() as connection:
            existing = self._find_document(connection, prepared.source)
            if self._is_current(existing, prepared.content_hash):
                return self._current_result(connection, existing)
            document_id = self._write_document(connection, existing, prepared)
            self._synchronize_chunks(connection, document_id, prepared.chunks)
            self._record_version(
                connection,
                document_id,
                prepared.content_hash,
                len(prepared.chunks),
            )
            row = self._find_document_by_id(connection, document_id)
        return DocumentImportResult(
            document=to_document(row),
            chunk_count=len(prepared.chunks),
            changed=True,
        )

    @staticmethod
    def _find_document(
        connection: sqlite3.Connection,
        source: str,
    ) -> sqlite3.Row | None:
        """Sucht ein importiertes Dokument anhand seines festen Quellpfads."""
        return connection.execute(
            "SELECT * FROM knowledge_documents WHERE source_path = ?",
            (source,),
        ).fetchone()

    @staticmethod
    def _find_document_by_id(
        connection: sqlite3.Connection,
        document_id: int,
    ) -> sqlite3.Row:
        """Liest Dokumentmetadaten anhand ihrer Datenbankkennung."""
        return connection.execute(
            "SELECT * FROM knowledge_documents WHERE id = ?",
            (document_id,),
        ).fetchone()

    @staticmethod
    def _is_current(row: sqlite3.Row | None, content_hash: str) -> bool:
        """Vergleicht eine vorhandene Dokumentversion über ihre SHA-256-Prüfsumme."""
        return row is not None and row["content_hash"] == content_hash

    def _current_result(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> DocumentImportResult:
        """Erzeugt das unveränderte Importergebnis aus aktueller Datenbanklage."""
        chunk_count = connection.execute(
            "SELECT COUNT(*) FROM knowledge_chunks WHERE document_id = ?",
            (row["id"],),
        ).fetchone()[0]
        return DocumentImportResult(to_document(row), chunk_count, False)

    def _write_document(
        self,
        connection: sqlite3.Connection,
        existing: sqlite3.Row | None,
        document: PreparedDocument,
    ) -> int:
        """Fügt Dokumentmetadaten ein oder aktualisiert deren bestehende Zeile."""
        if existing is None:
            return self._insert_document(connection, document)
        self._update_document(connection, existing["id"], document)
        return existing["id"]

    @staticmethod
    def _insert_document(
        connection: sqlite3.Connection,
        document: PreparedDocument,
    ) -> int:
        """Fügt neue Dokumentmetadaten ein und liefert ihre Kennung."""
        cursor = connection.execute(
            """
            INSERT INTO knowledge_documents (source_path, title, content_hash)
            VALUES (?, ?, ?)
            """,
            (document.source, document.title, document.content_hash),
        )
        return cursor.lastrowid

    @staticmethod
    def _update_document(
        connection: sqlite3.Connection,
        document_id: int,
        document: PreparedDocument,
    ) -> None:
        """Aktualisiert Titel, Prüfsumme und Importzeit eines Dokuments."""
        connection.execute(
            """
            UPDATE knowledge_documents
            SET title = ?, content_hash = ?, imported_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (document.title, document.content_hash, document_id),
        )

    @staticmethod
    def _synchronize_chunks(
        connection: sqlite3.Connection,
        document_id: int,
        chunks: tuple[str, ...],
    ) -> None:
        """Synchronisiert Abschnitte und entfernt nicht mehr vorhandene Teile."""
        existing = SQLiteKnowledgeLibrary._load_chunk_rows(
            connection,
            document_id,
        )
        by_index = {row["chunk_index"]: row for row in existing}
        for index, content in enumerate(chunks, 1):
            SQLiteKnowledgeLibrary._synchronize_chunk(
                connection,
                document_id,
                index,
                content,
                by_index.get(index),
            )
        connection.execute(
            "DELETE FROM knowledge_chunks WHERE document_id = ? AND chunk_index > ?",
            (document_id, len(chunks)),
        )

    @staticmethod
    def _load_chunk_rows(
        connection: sqlite3.Connection,
        document_id: int,
    ) -> tuple[sqlite3.Row, ...]:
        """Lädt bestehende Abschnittszeilen eines Dokuments in stabiler Reihenfolge."""
        return tuple(connection.execute(
            """
            SELECT id, chunk_index, content FROM knowledge_chunks
            WHERE document_id = ? ORDER BY chunk_index
            """,
            (document_id,),
        ).fetchall())

    @staticmethod
    def _synchronize_chunk(
        connection: sqlite3.Connection,
        document_id: int,
        index: int,
        content: str,
        existing: sqlite3.Row | None,
    ) -> None:
        """Erhält unveränderte Abschnitte oder ersetzt geänderte samt Vektorkaskade."""
        if existing is not None and existing["content"] == content:
            return
        if existing is not None:
            connection.execute(
                "DELETE FROM knowledge_chunks WHERE id = ?",
                (existing["id"],),
            )
        connection.execute(
            """
            INSERT INTO knowledge_chunks (document_id, chunk_index, content)
            VALUES (?, ?, ?)
            """,
            (document_id, index, content),
        )

    @staticmethod
    def _record_version(
        connection: sqlite3.Connection,
        document_id: int,
        content_hash: str,
        chunk_count: int,
    ) -> None:
        """Schreibt eine fortlaufende unveränderliche Dokumentversion."""
        connection.execute(
            """
            INSERT INTO knowledge_document_versions (
                document_id, version_number, content_hash, chunk_count
            ) VALUES (
                ?, COALESCE((SELECT MAX(version_number) + 1
                    FROM knowledge_document_versions WHERE document_id = ?), 1), ?, ?
            )
            """,
            (document_id, document_id, content_hash, chunk_count),
        )

    def list_documents(self, limit: int = 50) -> tuple[KnowledgeDocument, ...]:
        """Liefert die neuesten importierten Dokumenteinträge."""
        if limit < 1:
            raise ValueError("Document limit must be at least 1.")
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_documents ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(to_document(row) for row in rows)

    def list_all_documents(self) -> tuple[KnowledgeDocument, ...]:
        """Liefert das vollständige Inventar importierter Dokumente."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_documents ORDER BY id"
            ).fetchall()
        return tuple(to_document(row) for row in rows)

    def list_chunks(self, document_id: int) -> tuple[KnowledgeChunk, ...]:
        """Liefert alle Abschnitte eines importierten Dokuments."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT c.id, c.document_id, c.chunk_index, c.content,
                       d.source_path, d.title
                FROM knowledge_chunks AS c
                JOIN knowledge_documents AS d ON d.id = c.document_id
                WHERE c.document_id = ?
                ORDER BY c.chunk_index
                """,
                (document_id,),
            ).fetchall()
        return tuple(to_chunk(row) for row in rows)

    def list_document_versions(
        self,
        document_id: int,
    ) -> tuple[KnowledgeDocumentVersion, ...]:
        """Liefert gespeicherte Metadatenrevisionen eines Dokuments."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM knowledge_document_versions
                WHERE document_id = ? ORDER BY version_number DESC
                """,
                (document_id,),
            ).fetchall()
        return tuple(to_document_version(row) for row in rows)

    def document_exists(self, document_id: int) -> bool:
        """Meldet, ob eine Dokumentkennung noch vorhanden ist."""
        with self._connect() as connection:
            row = self._find_document_by_id(connection, document_id)
        return row is not None

    def search(self, query: str, limit: int = 5) -> tuple[KnowledgeChunk, ...]:
        """Liefert lexikalisch relevante Dokumentabschnitte zu einer Anfrage."""
        if limit < 1:
            raise ValueError("Knowledge limit must be at least 1.")
        terms = search_terms(query, self.TERM_MIN_LENGTH)
        if not terms:
            return ()
        rows = self._load_chunks()
        return rank_chunk_rows(rows, terms, limit)

    def _load_chunks(self) -> tuple[sqlite3.Row, ...]:
        """Lädt alle belegten Dokumentabschnitte für die lokale Suche."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT c.id, c.document_id, c.chunk_index, c.content,
                       d.source_path, d.title
                FROM knowledge_chunks AS c
                JOIN knowledge_documents AS d ON d.id = c.document_id
                ORDER BY c.id DESC
                """
            ).fetchall()
        return tuple(rows)

    def forget_document(self, document_id: int) -> bool:
        """Löscht ein Dokument und seine Abschnitte über Kaskadenregeln."""
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM knowledge_documents WHERE id = ?",
                (document_id,),
            )
        return cursor.rowcount > 0
