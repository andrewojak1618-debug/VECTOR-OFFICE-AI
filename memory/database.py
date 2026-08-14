import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from memory.models import MemoryEntry


class SQLiteMemoryStore:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row

        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    category TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def remember(
        self,
        content: str,
        category: str = "fact",
        source: str = "user-confirmed",
    ) -> MemoryEntry:
        normalized_content = content.strip()

        if not normalized_content:
            raise ValueError("Memory content must not be empty.")

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memories (content, category, source)
                VALUES (?, ?, ?)
                ON CONFLICT(content) DO UPDATE SET
                    category = excluded.category,
                    source = excluded.source
                """,
                (normalized_content, category, source),
            )
            row = connection.execute(
                "SELECT * FROM memories WHERE content = ? COLLATE NOCASE",
                (normalized_content,),
            ).fetchone()

        return self._to_entry(row)

    def list_memories(self, limit: int = 20) -> tuple[MemoryEntry, ...]:
        if limit < 1:
            raise ValueError("Memory limit must be at least 1.")

        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM memories ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()

        return tuple(self._to_entry(row) for row in rows)

    def search(self, query: str, limit: int = 5) -> tuple[MemoryEntry, ...]:
        if limit < 1:
            raise ValueError("Memory limit must be at least 1.")

        terms = {
            term
            for term in re.findall(r"\w+", query.casefold())
            if len(term) >= 4
        }

        if not terms:
            return ()

        candidates = self.list_memories(limit=200)
        scored = []

        for entry in candidates:
            content = entry.content.casefold()
            score = sum(term in content for term in terms)

            if score:
                scored.append((score, entry.id, entry))

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return tuple(item[2] for item in scored[:limit])

    def forget(self, memory_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM memories WHERE id = ?",
                (memory_id,),
            )

        return cursor.rowcount > 0

    @staticmethod
    def _to_entry(row: sqlite3.Row) -> MemoryEntry:
        return MemoryEntry(
            id=row["id"],
            content=row["content"],
            category=row["category"],
            source=row["source"],
            created_at=row["created_at"],
        )
