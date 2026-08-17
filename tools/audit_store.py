"""Persist sanitized tool audit metadata in a bounded local SQLite table."""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Iterator

from tools.permissions import PermissionLevel
from tools.registry import (
    ToolArguments,
    ToolAuditEvent,
    ToolResultStatus,
)


DEFAULT_AUDIT_RETENTION_DAYS = 30
DEFAULT_AUDIT_MAX_ENTRIES = 1_000
AUDIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS tool_audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_name TEXT NOT NULL,
    permission TEXT,
    arguments_json TEXT NOT NULL,
    status TEXT NOT NULL,
    error_code TEXT,
    occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tool_audit_occurred_at
    ON tool_audit_events(occurred_at);
"""


@dataclass(frozen=True)
class ToolAuditRecord:
    """Expose one locally persisted, already sanitized audit event."""

    id: int
    tool_name: str
    permission: PermissionLevel | None
    status: ToolResultStatus
    error_code: str | None
    occurred_at: str
    arguments: ToolArguments = field(
        default_factory=lambda: MappingProxyType({}),
    )


class SQLiteToolAuditStore:
    """Store redacted registry events and enforce age and count retention."""

    def __init__(
        self,
        database_path: str | Path,
        retention_days: int = DEFAULT_AUDIT_RETENTION_DAYS,
        max_entries: int = DEFAULT_AUDIT_MAX_ENTRIES,
    ):
        _validate_positive_int(retention_days, "Audit retention days")
        _validate_positive_int(max_entries, "Audit maximum entries")
        self.database_path = Path(database_path)
        self.retention_days = retention_days
        self.max_entries = max_entries
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def record(self, event: ToolAuditEvent) -> None:
        """Persist one sanitized registry event and apply retention."""
        if not isinstance(event, ToolAuditEvent):
            raise TypeError("Audit store accepts only ToolAuditEvent values.")
        permission = event.permission.value if event.permission else None
        arguments_json = _encode_arguments(event.arguments)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tool_audit_events (
                    tool_name, permission, arguments_json, status, error_code
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event.tool_name,
                    permission,
                    arguments_json,
                    event.status.value,
                    event.error_code,
                ),
            )
            self._prune_connection(connection)

    def list_events(self, limit: int = 50) -> tuple[ToolAuditRecord, ...]:
        """Return the newest sanitized audit records first."""
        _validate_positive_int(limit, "Audit list limit")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM tool_audit_events
                ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return tuple(_to_record(row) for row in rows)

    def prune(self) -> int:
        """Apply configured retention and return the deleted row count."""
        with self._connect() as connection:
            return self._prune_connection(connection)

    def clear(self) -> int:
        """Delete all local tool audit records and return the row count."""
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM tool_audit_events")
        return max(cursor.rowcount, 0)

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
            connection.executescript(AUDIT_SCHEMA)

    def _prune_connection(self, connection: sqlite3.Connection) -> int:
        age_cursor = connection.execute(
            """
            DELETE FROM tool_audit_events
            WHERE occurred_at < datetime('now', ?)
            """,
            (f"-{self.retention_days} days",),
        )
        count_cursor = connection.execute(
            """
            DELETE FROM tool_audit_events
            WHERE id NOT IN (
                SELECT id FROM tool_audit_events
                ORDER BY id DESC LIMIT ?
            )
            """,
            (self.max_entries,),
        )
        return max(age_cursor.rowcount, 0) + max(count_cursor.rowcount, 0)


def _encode_arguments(arguments: ToolArguments) -> str:
    return json.dumps(
        dict(arguments),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _to_record(row: sqlite3.Row) -> ToolAuditRecord:
    permission = (
        PermissionLevel(row["permission"])
        if row["permission"] is not None
        else None
    )
    arguments = MappingProxyType(json.loads(row["arguments_json"]))
    return ToolAuditRecord(
        id=row["id"],
        tool_name=row["tool_name"],
        permission=permission,
        status=ToolResultStatus(row["status"]),
        error_code=row["error_code"],
        occurred_at=row["occurred_at"],
        arguments=arguments,
    )


def _validate_positive_int(value: int, label: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{label} must be a positive integer.")
