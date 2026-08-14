"""Controlled local document storage and lexical retrieval."""

import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from memory.document_text import DocumentTextProcessor, PreparedDocument
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
    TERM_MIN_LENGTH = 4

    def __init__(
        self,
        database_path: str | Path,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_file_bytes = max_file_bytes
        self.chunk_size = chunk_size
        self.text_processor = DocumentTextProcessor(max_file_bytes, chunk_size)
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
            initialize_knowledge_schema(connection)

    def import_document(self, source_path: str | Path) -> DocumentImportResult:
        """Import or atomically refresh one approved UTF-8 document."""
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
            document=self._to_document(row),
            chunk_count=len(prepared.chunks),
            changed=True,
        )

    @staticmethod
    def _find_document(
        connection: sqlite3.Connection,
        source: str,
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM knowledge_documents WHERE source_path = ?",
            (source,),
        ).fetchone()

    @staticmethod
    def _find_document_by_id(
        connection: sqlite3.Connection,
        document_id: int,
    ) -> sqlite3.Row:
        return connection.execute(
            "SELECT * FROM knowledge_documents WHERE id = ?",
            (document_id,),
        ).fetchone()

    @staticmethod
    def _is_current(row: sqlite3.Row | None, content_hash: str) -> bool:
        return row is not None and row["content_hash"] == content_hash

    def _current_result(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> DocumentImportResult:
        chunk_count = connection.execute(
            "SELECT COUNT(*) FROM knowledge_chunks WHERE document_id = ?",
            (row["id"],),
        ).fetchone()[0]
        return DocumentImportResult(self._to_document(row), chunk_count, False)

    def _write_document(
        self,
        connection: sqlite3.Connection,
        existing: sqlite3.Row | None,
        document: PreparedDocument,
    ) -> int:
        if existing is None:
            return self._insert_document(connection, document)
        self._update_document(connection, existing["id"], document)
        return existing["id"]

    @staticmethod
    def _insert_document(
        connection: sqlite3.Connection,
        document: PreparedDocument,
    ) -> int:
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
        """Return the newest imported document records."""
        if limit < 1:
            raise ValueError("Document limit must be at least 1.")
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_documents ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(self._to_document(row) for row in rows)

    def list_all_documents(self) -> tuple[KnowledgeDocument, ...]:
        """Return the complete imported document inventory."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_documents ORDER BY id"
            ).fetchall()
        return tuple(self._to_document(row) for row in rows)

    def list_chunks(self, document_id: int) -> tuple[KnowledgeChunk, ...]:
        """Return all sections belonging to one imported document."""
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
        return tuple(self._to_chunk(row) for row in rows)

    def list_document_versions(
        self,
        document_id: int,
    ) -> tuple[KnowledgeDocumentVersion, ...]:
        """Return recorded metadata revisions for one document."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM knowledge_document_versions
                WHERE document_id = ? ORDER BY version_number DESC
                """,
                (document_id,),
            ).fetchall()
        return tuple(self._to_document_version(row) for row in rows)

    def document_exists(self, document_id: int) -> bool:
        """Report whether one document identifier is still present."""
        with self._connect() as connection:
            row = self._find_document_by_id(connection, document_id)
        return row is not None

    def search(self, query: str, limit: int = 5) -> tuple[KnowledgeChunk, ...]:
        """Return lexically relevant document chunks for a query."""
        if limit < 1:
            raise ValueError("Knowledge limit must be at least 1.")
        terms = self._search_terms(query)
        if not terms:
            return ()
        rows = self._load_chunks()
        return self._rank_chunks(rows, terms, limit)

    def _load_chunks(self) -> tuple[sqlite3.Row, ...]:
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

    def _rank_chunks(
        self,
        rows: tuple[sqlite3.Row, ...],
        terms: frozenset[str],
        limit: int,
    ) -> tuple[KnowledgeChunk, ...]:
        scored = []
        for row in rows:
            text = f"{row['title']} {row['content']}".casefold()
            score = sum(term in text for term in terms)
            if score:
                scored.append((score, row["id"], self._to_chunk(row)))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return tuple(item[2] for item in scored[:limit])

    def forget_document(self, document_id: int) -> bool:
        """Delete one document and its chunks through cascade semantics."""
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM knowledge_documents WHERE id = ?",
                (document_id,),
            )
        return cursor.rowcount > 0

    @classmethod
    def _search_terms(cls, query: str) -> frozenset[str]:
        return frozenset(
            term
            for term in re.findall(r"\w+", query.casefold())
            if len(term) >= cls.TERM_MIN_LENGTH
        )

    @staticmethod
    def _to_document(row: sqlite3.Row) -> KnowledgeDocument:
        return KnowledgeDocument(
            id=row["id"],
            source_path=row["source_path"],
            title=row["title"],
            content_hash=row["content_hash"],
            imported_at=row["imported_at"],
        )

    @staticmethod
    def _to_chunk(row: sqlite3.Row) -> KnowledgeChunk:
        return KnowledgeChunk(
            id=row["id"],
            document_id=row["document_id"],
            source_path=row["source_path"],
            title=row["title"],
            chunk_index=row["chunk_index"],
            content=row["content"],
        )

    @staticmethod
    def _to_document_version(row: sqlite3.Row) -> KnowledgeDocumentVersion:
        return KnowledgeDocumentVersion(
            id=row["id"],
            document_id=row["document_id"],
            version_number=row["version_number"],
            content_hash=row["content_hash"],
            chunk_count=row["chunk_count"],
            imported_at=row["imported_at"],
        )
