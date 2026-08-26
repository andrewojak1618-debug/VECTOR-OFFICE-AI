"""Tests für die inhaltsfreie Abfrage der letzten kontrollierten Tool-Aktion."""

import tempfile
import unittest
from pathlib import Path
from types import MappingProxyType

from tools.audit_store import SQLiteToolAuditStore, ToolAuditRecord
from tools.latest_tool_status import (
    TOOL_NAME,
    create_latest_tool_status_reader,
    register_latest_tool_status_tool,
)
from tools.permissions import PermissionLevel
from tools.registry import ToolAuditEvent, ToolRegistry
from tools.registry_types import ToolResultStatus


class LatestToolStatusTests(unittest.TestCase):
    """Sichert die lokale, redigierte und rein lesende Statusabfrage ab."""

    def test_definition_is_argument_free_and_read_only(self):
        registry = ToolRegistry()
        register_latest_tool_status_tool(registry, lambda: None)
        definition = registry.definitions()[0]

        self.assertEqual(TOOL_NAME, definition.name)
        self.assertEqual(PermissionLevel.READ_ONLY, definition.permission)
        self.assertEqual((), definition.parameters)

    def test_empty_audit_returns_safe_absence(self):
        registry = ToolRegistry()
        register_latest_tool_status_tool(registry, lambda: None)

        result = registry.execute(TOOL_NAME, {})

        self.assertTrue(result.succeeded)
        self.assertFalse(result.output["found"])
        self.assertIn("keine kontrollierte Aktion", result.output["spoken_text"])

    def test_known_action_returns_only_fixed_label_and_status(self):
        private_path = r"C:\private\secret.txt"
        record = _record(
            "development.open_project_directory",
            ToolResultStatus.SUCCESS,
            {"path": private_path},
            "private_error",
        )
        registry = ToolRegistry()
        register_latest_tool_status_tool(registry, lambda: record)

        result = registry.execute(TOOL_NAME, {})
        serialized = " ".join(map(str, result.output.values()))

        self.assertTrue(result.succeeded)
        self.assertEqual("Dokumentationsordner öffnen", result.output["action"])
        self.assertEqual("success", result.output["status"])
        self.assertNotIn(private_path, serialized)
        self.assertNotIn("private_error", serialized)
        self.assertNotIn("directory", serialized.casefold())

    def test_failed_action_uses_fixed_nontechnical_wording(self):
        record = _record(
            "development.run_core_tests",
            ToolResultStatus.FAILED,
            {},
            "private_failure_detail",
        )
        registry = ToolRegistry()
        register_latest_tool_status_tool(registry, lambda: record)

        result = registry.execute(TOOL_NAME, {})

        self.assertTrue(result.succeeded)
        self.assertIn("nicht erfolgreich", result.output["spoken_text"])
        self.assertNotIn("private_failure_detail", str(result.output))

    def test_unknown_audit_name_is_safely_rejected(self):
        registry = ToolRegistry()
        register_latest_tool_status_tool(
            registry,
            lambda: _record("unknown.private_tool", ToolResultStatus.SUCCESS),
        )

        result = registry.execute(TOOL_NAME, {})

        self.assertEqual(ToolResultStatus.FAILED, result.status)
        self.assertEqual("tool_execution_failed", result.error_code)
        self.assertNotIn("unknown.private_tool", result.message)

    def test_reader_skips_query_itself_and_unknown_events(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = SQLiteToolAuditStore(Path(temporary_directory) / "audit.db")
            store.record(_event("development.open_project_document"))
            store.record(_event("unknown.private_tool"))
            store.record(_event(TOOL_NAME))
            reader = create_latest_tool_status_reader(store)

            record = reader()

        self.assertIsNotNone(record)
        self.assertEqual("development.open_project_document", record.tool_name)


def _record(
    tool_name: str,
    status: ToolResultStatus,
    arguments=None,
    error_code: str | None = None,
) -> ToolAuditRecord:
    """Erzeugt einen kontrollierten Audit-Datensatz für einen Einzeltest."""
    return ToolAuditRecord(
        1,
        tool_name,
        PermissionLevel.READ_ONLY,
        status,
        error_code,
        "2026-08-26 20:00:00",
        MappingProxyType(arguments or {}),
    )


def _event(tool_name: str) -> ToolAuditEvent:
    """Erzeugt ein inhaltsfreies erfolgreiches Audit-Ereignis."""
    return ToolAuditEvent(
        tool_name,
        PermissionLevel.READ_ONLY,
        MappingProxyType({}),
        ToolResultStatus.SUCCESS,
        None,
    )


if __name__ == "__main__":
    unittest.main()
