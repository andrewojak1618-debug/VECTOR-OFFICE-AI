"""Command tests for local tool audit inspection and maintenance."""

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from diagnostics.tool_audit import main
from tools.audit_store import SQLiteToolAuditStore
from tools.permissions import PermissionLevel
from tools.registry import ToolAuditEvent, ToolResultStatus


class ToolAuditDiagnosticTests(unittest.TestCase):
    """Keep audit maintenance local, readable, and confirmation-bound."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary.name) / "audit.db"
        self.settings = SimpleNamespace(
            MEMORY_DB_PATH=self.database_path,
            TOOL_AUDIT_RETENTION_DAYS=30,
            TOOL_AUDIT_MAX_ENTRIES=100,
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_list_prints_only_persisted_sanitized_metadata(self):
        store = SQLiteToolAuditStore(self.database_path)
        store.record(ToolAuditEvent(
            "vector.perform_action",
            PermissionLevel.MUTATING,
            {"action": "greeting"},
            ToolResultStatus.SUCCESS,
            None,
        ))

        code, output = self._run(("list", "--limit", "1"))

        self.assertEqual(0, code)
        self.assertIn("vector.perform_action", output)
        self.assertIn('{"action":"greeting"}', output)

    def test_clear_requires_exact_confirmation(self):
        store = SQLiteToolAuditStore(self.database_path)
        store.record(_event())

        blocked, _output = self._run(("clear",))
        cleared, _output = self._run(("clear", "--confirm", "DELETE"))

        self.assertEqual(2, blocked)
        self.assertEqual(0, cleared)
        self.assertEqual((), store.list_events())

    def test_invalid_limit_returns_sanitized_failure(self):
        code, output = self._run(("list", "--limit", "0"))

        self.assertEqual(1, code)
        self.assertIn("could not be read", output)

    def _run(self, arguments):
        output = io.StringIO()
        with patch("diagnostics.tool_audit.settings", self.settings):
            with redirect_stdout(output):
                code = main(arguments)
        return code, output.getvalue()


def _event() -> ToolAuditEvent:
    return ToolAuditEvent(
        "vector.list_actions",
        PermissionLevel.READ_ONLY,
        {},
        ToolResultStatus.SUCCESS,
        None,
    )


if __name__ == "__main__":
    unittest.main()
