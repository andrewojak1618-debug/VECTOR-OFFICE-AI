"""Controlled local document storage and lexical retrieval."""

import hashlib
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from memory.models import (
    DocumentImportResult,
    KnowledgeChunk,
    KnowledgeDocument,
)


@dataclass(frozen=True)
class _PreparedDocument:
    path: Path
    source: str
    title: str
    content_hash: str
    chunks: tuple[str, ...]


class SQLiteKnowledgeLibrary:
    """Store explicitly imported documents in a local SQLite database."""

    ALLOWED_EXTENSIONS = frozenset({".md", ".txt"})
    DEFAULT_MAX_FILE_BYTES = 2 * 1024 * 1024
    DEFAULT_CHUNK_SIZE = 1000
    MIN_CHUNK_SIZE = 100
    TERM_MIN_LENGTH = 4

    def __init__(
        self,
        database_path: str | Path,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ):
        self._validate_limits(max_file_bytes, chunk_size)
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_file_bytes = max_file_bytes
        self.chunk_size = chunk_size
        self._initialize()

    @staticmethod
    def _validate_limits(max_file_bytes: int, chunk_size: int) -> None:
        if max_file_bytes < 1:
            raise ValueError("Maximum file size must be at least 1 byte.")
        if chunk_size < SQLiteKnowledgeLibrary.MIN_CHUNK_SIZE:
            raise ValueError("Chunk size must be at least 100 characters.")

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
            connection.executescript(
                """
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
                    FOREIGN KEY(document_id)
                        REFERENCES knowledge_documents(id)
                        ON DELETE CASCADE,
                    UNIQUE(document_id, chunk_index)
                );
                """
            )

    def import_document(self, source_path: str | Path) -> DocumentImportResult:
        """Import or atomically refresh one approved UTF-8 document."""
        prepared = self._prepare_document(source_path)
        with self._connect() as connection:
            existing = self._find_document(connection, prepared.source)
            if self._is_current(existing, prepared.content_hash):
                return self._current_result(connection, existing)
            document_id = self._write_document(connection, existing, prepared)
            self._replace_chunks(connection, document_id, prepared.chunks)
            row = self._find_document_by_id(connection, document_id)
        return DocumentImportResult(
            document=self._to_document(row),
            chunk_count=len(prepared.chunks),
            changed=True,
        )

    def _prepare_document(self, source_path: str | Path) -> _PreparedDocument:
        path = self._resolve_document_path(source_path)
        content = self._read_document(path)
        normalized = content.strip()
        if not normalized:
            raise ValueError("Document must not be empty.")
        return _PreparedDocument(
            path=path,
            source=str(path),
            title=path.stem,
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            chunks=self._split_content(normalized),
        )

    def _resolve_document_path(self, source_path: str | Path) -> Path:
        path_text = str(source_path).strip().strip('"')
        path = Path(path_text).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"Document does not exist: {path}")
        if path.suffix.casefold() not in self.ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(self.ALLOWED_EXTENSIONS))
            raise ValueError(f"Only these document types are allowed: {allowed}")
        if path.stat().st_size > self.max_file_bytes:
            raise ValueError(f"Document exceeds the {self.max_file_bytes}-byte limit.")
        return path

    @staticmethod
    def _read_document(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Document must be UTF-8 encoded.") from exc

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
        document: _PreparedDocument,
    ) -> int:
        if existing is None:
            return self._insert_document(connection, document)
        self._update_document(connection, existing["id"], document)
        return existing["id"]

    @staticmethod
    def _insert_document(
        connection: sqlite3.Connection,
        document: _PreparedDocument,
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
        document: _PreparedDocument,
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
    def _replace_chunks(
        connection: sqlite3.Connection,
        document_id: int,
        chunks: tuple[str, ...],
    ) -> None:
        connection.execute(
            "DELETE FROM knowledge_chunks WHERE document_id = ?",
            (document_id,),
        )
        connection.executemany(
            """
            INSERT INTO knowledge_chunks (document_id, chunk_index, content)
            VALUES (?, ?, ?)
            """,
            ((document_id, index, chunk) for index, chunk in enumerate(chunks, 1)),
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

    def _split_content(self, content: str) -> tuple[str, ...]:
        chunks: list[str] = []
        current = ""
        for paragraph in re.split(r"\n\s*\n", content):
            for part in self._split_long_paragraph(paragraph.strip()):
                current = self._append_part(chunks, current, part)
        if current:
            chunks.append(current)
        return tuple(chunks)

    def _append_part(self, chunks: list[str], current: str, part: str) -> str:
        if not part:
            return current
        candidate = f"{current}\n\n{part}" if current else part
        if len(candidate) <= self.chunk_size:
            return candidate
        chunks.append(current)
        return part

    def _split_long_paragraph(self, paragraph: str) -> tuple[str, ...]:
        if not paragraph or len(paragraph) <= self.chunk_size:
            return (paragraph,) if paragraph else ()
        parts: list[str] = []
        current = ""
        for word in paragraph.split():
            if len(word) > self.chunk_size:
                current = self._append_long_word(parts, current, word)
                continue
            current = self._append_word(parts, current, word)
        if current:
            parts.append(current)
        return tuple(parts)

    def _append_long_word(self, parts: list[str], current: str, word: str) -> str:
        if current:
            parts.append(current)
        parts.extend(
            word[index:index + self.chunk_size]
            for index in range(0, len(word), self.chunk_size)
        )
        return ""

    def _append_word(self, parts: list[str], current: str, word: str) -> str:
        candidate = f"{current} {word}" if current else word
        if len(candidate) <= self.chunk_size:
            return candidate
        parts.append(current)
        return word

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
