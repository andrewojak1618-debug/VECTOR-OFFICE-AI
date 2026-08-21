"""Persistence and retention tests for sanitized local tool audits."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from application.runtime import _create_audit_store, _create_tool_registry
from memory.database import SQLiteMemoryStore
from tools.audit_store import SQLiteToolAuditStore
from tools.permissions import PermissionLevel
from tools.registry import (
    REDACTED_ARGUMENT,
    ToolAuditEvent,
    ToolDefinition,
    ToolRegistry,
    ToolResultStatus,
)
from tools.test_tools import EchoTestTool


class OutputOnlyTool:
    """Return private test output that must never enter audit storage."""

    @property
    def definition(self):
        """Describe a side-effect-free test tool without arguments."""
        return ToolDefinition(
            "test.output",
            "Return private test output.",
            PermissionLevel.READ_ONLY,
        )

    def execute(self, arguments):
        """Return a value excluded from ToolAuditEvent by design."""
        return {"private_output": "output-must-not-be-stored"}


class SQLiteToolAuditStoreTests(unittest.TestCase):
    """Keep persisted audit metadata local, sanitized, and bounded."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary.name) / "memory.db"

    def tearDown(self):
        self.temporary.cleanup()

    def test_registry_success_is_persisted_with_redacted_arguments(self):
        store = SQLiteToolAuditStore(self.database_path)
        registry = ToolRegistry(audit_sink=store.record)
        registry.register(EchoTestTool())
        secret = "audit-secret-value"

        result = registry.execute(
            "test.echo",
            {"text": "sichtbar", "secret": secret},
        )
        record = store.list_events()[0]

        self.assertTrue(result.succeeded)
        self.assertEqual("test.echo", record.tool_name)
        self.assertEqual(PermissionLevel.READ_ONLY, record.permission)
        self.assertEqual(ToolResultStatus.SUCCESS, record.status)
        self.assertEqual(REDACTED_ARGUMENT, record.arguments["secret"])
        self.assertNotIn(secret.encode(), self.database_path.read_bytes())

    def test_unknown_tool_persists_no_supplied_arguments(self):
        store = SQLiteToolAuditStore(self.database_path)
        registry = ToolRegistry(audit_sink=store.record)

        registry.execute("unknown.tool", {"secret": "must-not-persist"})
        record = store.list_events()[0]

        self.assertEqual("tool_not_registered", record.error_code)
        self.assertEqual({}, dict(record.arguments))
        self.assertNotIn(b"must-not-persist", self.database_path.read_bytes())

    def test_tool_output_is_never_part_of_the_audit_record(self):
        store = SQLiteToolAuditStore(self.database_path)
        registry = ToolRegistry(audit_sink=store.record)
        registry.register(OutputOnlyTool())

        registry.execute("test.output", {})

        self.assertEqual({}, dict(store.list_events()[0].arguments))
        self.assertNotIn(
            b"output-must-not-be-stored",
            self.database_path.read_bytes(),
        )

    def test_maximum_entry_retention_keeps_only_newest_rows(self):
        store = SQLiteToolAuditStore(
            self.database_path,
            retention_days=30,
            max_entries=2,
        )

        for name in ("test.first", "test.second", "test.third"):
            store.record(_event(name))

        self.assertEqual(
            ("test.third", "test.second"),
            tuple(record.tool_name for record in store.list_events()),
        )

    def test_age_retention_removes_expired_rows(self):
        store = SQLiteToolAuditStore(
            self.database_path,
            retention_days=7,
            max_entries=10,
        )
        store.record(_event("test.old"))
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                "UPDATE tool_audit_events SET occurred_at = '2000-01-01 00:00:00'"
            )
            connection.commit()
        finally:
            connection.close()

        deleted = store.prune()

        self.assertEqual(1, deleted)
        self.assertEqual((), store.list_events())

    def test_clear_removes_only_audit_rows(self):
        memory = SQLiteMemoryStore(self.database_path)
        memory.remember("Bestätigte Erinnerung")
        store = SQLiteToolAuditStore(self.database_path)
        store.record(_event("test.local"))

        deleted = store.clear()

        self.assertEqual(1, deleted)
        self.assertEqual((), store.list_events())
        self.assertEqual(1, len(memory.list_memories()))

    def test_invalid_retention_and_event_types_are_rejected(self):
        with self.assertRaises(ValueError):
            SQLiteToolAuditStore(self.database_path, retention_days=0)
        with self.assertRaises(ValueError):
            SQLiteToolAuditStore(self.database_path, max_entries=True)
        store = SQLiteToolAuditStore(self.database_path)
        with self.assertRaises(TypeError):
            store.record("not-an-event")

    def test_audit_sink_failure_never_blocks_tool_success(self):
        def fail(_event):
            raise sqlite3.OperationalError("private database detail")

        registry = ToolRegistry(audit_sink=fail)
        registry.register(OutputOnlyTool())

        result = registry.execute("test.output", {})

        self.assertTrue(result.succeeded)


class AuditRuntimeIntegrationTests(unittest.TestCase):
    """Connect optional persistence only through the production registry sink."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary.name) / "runtime.db"

    def tearDown(self):
        self.temporary.cleanup()

    def test_runtime_registry_writes_read_only_event_without_robot_action(self):
        settings = _settings(self.database_path)
        store = _create_audit_store(settings)
        actions = MagicMock()
        actions.available_actions.return_value = ("greeting",)
        registry = _create_tool_registry(actions, store)

        result = registry.execute("vector.list_actions", {})

        self.assertTrue(result.succeeded)
        self.assertEqual("vector.list_actions", store.list_events()[0].tool_name)
        actions.perform.assert_not_called()

    def test_disabled_audit_creates_no_database(self):
        settings = _settings(self.database_path, TOOL_AUDIT_ENABLED=False)

        store = _create_audit_store(settings)

        self.assertIsNone(store)
        self.assertFalse(self.database_path.exists())

    def test_initialization_failure_is_sanitized_and_nonfatal(self):
        settings = _settings(self.database_path)
        failure = sqlite3.OperationalError("private database path")

        with patch(
            "application.runtime_resources.SQLiteToolAuditStore",
            side_effect=failure,
        ), patch("builtins.print") as output:
            store = _create_audit_store(settings)

        self.assertIsNone(store)
        self.assertNotIn("private database path", str(output.call_args))


def _event(tool_name: str) -> ToolAuditEvent:
    return ToolAuditEvent(
        tool_name,
        PermissionLevel.READ_ONLY,
        {},
        ToolResultStatus.SUCCESS,
        None,
    )


def _settings(database_path: Path, **overrides):
    values = {
        "MEMORY_DB_PATH": database_path,
        "TOOL_AUDIT_ENABLED": True,
        "TOOL_AUDIT_RETENTION_DAYS": 30,
        "TOOL_AUDIT_MAX_ENTRIES": 100,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


if __name__ == "__main__":
    unittest.main()
