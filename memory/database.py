"""SQLite-backed, user-confirmed long-term memory."""

import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from memory.exporting import LocalDataExporter
from memory.models import MemoryEntry, MemoryStatistics


MIN_SEARCH_TERM_LENGTH = 4
SEARCH_CANDIDATE_LIMIT = 200


class SQLiteMemoryStore:
    """Persist only memories that the user explicitly confirms."""

    def __init__(self, database_path: str | Path):
        """Initialisiert die lokale SQLite-Ablage und legt ihr Schema an."""
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Öffnet eine transaktionale SQLite-Verbindung und schließt sie zuverlässig."""
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        """Legt die additive Tabelle für bestätigte Erinnerungen an."""
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
        """Fügt eine ausdrücklich bestätigte Erinnerung ein oder aktualisiert sie."""
        normalized_content = content.strip()
        if not normalized_content:
            raise ValueError("Memory content must not be empty.")
        with self._connect() as connection:
            self._upsert(connection, normalized_content, category, source)
            row = self._find_by_content(connection, normalized_content)
        return self._to_entry(row)

    @staticmethod
    def _upsert(connection, content: str, category: str, source: str) -> None:
        """Speichert eine Erinnerung anhand ihres inhaltsbezogenen Eindeutigkeitsschlüssels."""
        connection.execute(
            """
            INSERT INTO memories (content, category, source)
            VALUES (?, ?, ?)
            ON CONFLICT(content) DO UPDATE SET
                category = excluded.category,
                source = excluded.source
            """,
            (content, category, source),
        )

    @staticmethod
    def _find_by_content(connection, content: str) -> sqlite3.Row:
        """Liest eine Erinnerung ohne Beachtung der Groß- und Kleinschreibung."""
        return connection.execute(
            "SELECT * FROM memories WHERE content = ? COLLATE NOCASE",
            (content,),
        ).fetchone()

    def list_memories(self, limit: int = 20) -> tuple[MemoryEntry, ...]:
        """Liefert die neuesten bestätigten Erinnerungen zuerst."""
        self._validate_limit(limit)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM memories ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(self._to_entry(row) for row in rows)

    def list_feedback(self, limit: int = 5) -> tuple[MemoryEntry, ...]:
        """Liefert ausschließlich ausdrücklich bestätigtes Kommunikationsfeedback."""
        self._validate_limit(limit)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM memories
                WHERE category = 'feedback'
                ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return tuple(self._to_entry(row) for row in rows)

    def status(self) -> MemoryStatistics:
        """Liefert reine Zählwerte zu bestätigten Erinnerungen und Feedback."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN category = 'feedback' THEN 1 ELSE 0 END)
                           AS feedback
                FROM memories
                """
            ).fetchone()
        feedback = int(row["feedback"] or 0)
        return MemoryStatistics(int(row["total"]) - feedback, feedback)

    def search(self, query: str, limit: int = 5) -> tuple[MemoryEntry, ...]:
        """Liefert Erinnerungen nach passenden aussagekräftigen Suchbegriffen sortiert."""
        self._validate_limit(limit)
        terms = self._search_terms(query)
        if not terms:
            return ()
        candidates = self._search_candidates()
        return self._rank(candidates, terms, limit)

    def _search_candidates(self) -> tuple[MemoryEntry, ...]:
        """Lädt eine feste Höchstzahl aktueller Erinnerungen ohne Stilfeedback."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM memories
                WHERE category != 'feedback'
                ORDER BY id DESC LIMIT ?
                """,
                (SEARCH_CANDIDATE_LIMIT,),
            ).fetchall()
        return tuple(self._to_entry(row) for row in rows)

    @staticmethod
    def _search_terms(query: str) -> frozenset[str]:
        """Extrahiert eindeutige normalisierte Suchbegriffe ab der Mindestlänge."""
        return frozenset(
            term
            for term in re.findall(r"\w+", query.casefold())
            if len(term) >= MIN_SEARCH_TERM_LENGTH
        )

    @staticmethod
    def _rank(candidates, terms: frozenset[str], limit: int):
        """Sortiert Kandidaten nach Begriffsüberschneidung und Aktualität."""
        scored = []
        for entry in candidates:
            score = sum(term in entry.content.casefold() for term in terms)
            if score:
                scored.append((score, entry.id, entry))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return tuple(item[2] for item in scored[:limit])

    def forget(self, memory_id: int) -> bool:
        """Löscht eine Erinnerung nach Kennung und meldet ihren vorherigen Bestand."""
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM memories WHERE id = ?",
                (memory_id,),
            )
        return cursor.rowcount > 0

    def export_confirmed_memories(self, destination: str | Path) -> Path:
        """Exportiert alle bestätigten Erinnerungen in eine bereinigte JSON-Datei."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM memories ORDER BY id"
            ).fetchall()
        memories = tuple(self._to_entry(row) for row in rows)
        return LocalDataExporter().export_memories(destination, memories)

    @staticmethod
    def _validate_limit(limit: int) -> None:
        """Verlangt für Speicherabfragen eine positive Ergebnisgrenze."""
        if limit < 1:
            raise ValueError("Memory limit must be at least 1.")

    @staticmethod
    def _to_entry(row: sqlite3.Row) -> MemoryEntry:
        """Überführt eine SQLite-Zeile in einen unveränderlichen Speichereintrag."""
        return MemoryEntry(
            id=row["id"],
            content=row["content"],
            category=row["category"],
            source=row["source"],
            created_at=row["created_at"],
        )
