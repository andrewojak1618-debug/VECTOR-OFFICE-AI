import hashlib
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from memory.models import (
    DocumentImportResult,
    KnowledgeChunk,
    KnowledgeDocument,
)


class SQLiteKnowledgeLibrary:
    """Controlled, local document library backed by SQLite."""

    ALLOWED_EXTENSIONS = frozenset({".md", ".txt"})

    def __init__(
        self,
        database_path: str | Path,
        max_file_bytes: int = 2 * 1024 * 1024,
        chunk_size: int = 1000,
    ):
        if max_file_bytes < 1:
            raise ValueError("Maximum file size must be at least 1 byte.")
        if chunk_size < 100:
            raise ValueError("Chunk size must be at least 100 characters.")

        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_file_bytes = max_file_bytes
        self.chunk_size = chunk_size
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
        path_text = str(source_path).strip()
        if len(path_text) >= 2 and path_text[0] == path_text[-1] == '"':
            path_text = path_text[1:-1]

        path = Path(path_text).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"Document does not exist: {path}")
        if path.suffix.casefold() not in self.ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(self.ALLOWED_EXTENSIONS))
            raise ValueError(f"Only these document types are allowed: {allowed}")
        if path.stat().st_size > self.max_file_bytes:
            raise ValueError(
                f"Document exceeds the {self.max_file_bytes}-byte limit."
            )

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Document must be UTF-8 encoded.") from exc

        normalized_content = content.strip()
        if not normalized_content:
            raise ValueError("Document must not be empty.")

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        chunks = self._split_content(normalized_content)
        source = str(path)
        title = path.stem

        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM knowledge_documents WHERE source_path = ?",
                (source,),
            ).fetchone()

            if existing is not None and existing["content_hash"] == content_hash:
                chunk_count = connection.execute(
                    "SELECT COUNT(*) FROM knowledge_chunks WHERE document_id = ?",
                    (existing["id"],),
                ).fetchone()[0]
                return DocumentImportResult(
                    document=self._to_document(existing),
                    chunk_count=chunk_count,
                    changed=False,
                )

            if existing is None:
                cursor = connection.execute(
                    """
                    INSERT INTO knowledge_documents
                        (source_path, title, content_hash)
                    VALUES (?, ?, ?)
                    """,
                    (source, title, content_hash),
                )
                document_id = cursor.lastrowid
            else:
                document_id = existing["id"]
                connection.execute(
                    """
                    UPDATE knowledge_documents
                    SET title = ?, content_hash = ?, imported_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (title, content_hash, document_id),
                )
                connection.execute(
                    "DELETE FROM knowledge_chunks WHERE document_id = ?",
                    (document_id,),
                )

            connection.executemany(
                """
                INSERT INTO knowledge_chunks
                    (document_id, chunk_index, content)
                VALUES (?, ?, ?)
                """,
                (
                    (document_id, index, chunk)
                    for index, chunk in enumerate(chunks, start=1)
                ),
            )
            row = connection.execute(
                "SELECT * FROM knowledge_documents WHERE id = ?",
                (document_id,),
            ).fetchone()

        return DocumentImportResult(
            document=self._to_document(row),
            chunk_count=len(chunks),
            changed=True,
        )

    def list_documents(self, limit: int = 50) -> tuple[KnowledgeDocument, ...]:
        if limit < 1:
            raise ValueError("Document limit must be at least 1.")

        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_documents ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()

        return tuple(self._to_document(row) for row in rows)

    def search(self, query: str, limit: int = 5) -> tuple[KnowledgeChunk, ...]:
        if limit < 1:
            raise ValueError("Knowledge limit must be at least 1.")

        terms = {
            term
            for term in re.findall(r"\w+", query.casefold())
            if len(term) >= 4
        }
        if not terms:
            return ()

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    c.id,
                    c.document_id,
                    c.chunk_index,
                    c.content,
                    d.source_path,
                    d.title
                FROM knowledge_chunks AS c
                JOIN knowledge_documents AS d ON d.id = c.document_id
                ORDER BY c.id DESC
                """
            ).fetchall()

        scored = []
        for row in rows:
            searchable_text = f"{row['title']} {row['content']}".casefold()
            score = sum(term in searchable_text for term in terms)
            if score:
                scored.append((score, row["id"], self._to_chunk(row)))

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return tuple(item[2] for item in scored[:limit])

    def forget_document(self, document_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM knowledge_documents WHERE id = ?",
                (document_id,),
            )
        return cursor.rowcount > 0

    def _split_content(self, content: str) -> tuple[str, ...]:
        paragraphs = re.split(r"\n\s*\n", content)
        chunks: list[str] = []
        current = ""

        for paragraph in paragraphs:
            normalized = paragraph.strip()
            if not normalized:
                continue

            for part in self._split_long_paragraph(normalized):
                candidate = f"{current}\n\n{part}" if current else part
                if len(candidate) <= self.chunk_size:
                    current = candidate
                else:
                    chunks.append(current)
                    current = part

        if current:
            chunks.append(current)

        return tuple(chunks)

    def _split_long_paragraph(self, paragraph: str) -> tuple[str, ...]:
        if len(paragraph) <= self.chunk_size:
            return (paragraph,)

        parts: list[str] = []
        current = ""
        for word in paragraph.split():
            if len(word) > self.chunk_size:
                if current:
                    parts.append(current)
                    current = ""
                parts.extend(
                    word[index:index + self.chunk_size]
                    for index in range(0, len(word), self.chunk_size)
                )
                continue

            candidate = f"{current} {word}" if current else word
            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                parts.append(current)
                current = word

        if current:
            parts.append(current)
        return tuple(parts)

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
