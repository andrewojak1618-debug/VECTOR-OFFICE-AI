"""Tests for the fixed, content-free project document catalog."""

import tempfile
import unittest
from pathlib import Path

from tools.permissions import PermissionLevel
from tools.project_documents import (
    DOCUMENT_COUNT,
    ProjectDocumentCatalogStatus,
    register_project_document_catalog_tool,
)
from tools.registry import ToolRegistry
from tools.registry_types import ToolResultStatus


class ProjectDocumentCatalogToolTests(unittest.TestCase):
    def test_definition_is_argumentless_and_read_only(self):
        registry = self._registry(ProjectDocumentCatalogStatus(("valid",) * DOCUMENT_COUNT))
        definition = registry.definitions()[0]

        self.assertEqual("development.project_document_catalog", definition.name)
        self.assertEqual(PermissionLevel.READ_ONLY, definition.permission)
        self.assertEqual((), definition.parameters)

    def test_complete_catalog_returns_only_safe_fixed_metadata(self):
        registry = self._registry(ProjectDocumentCatalogStatus(("valid",) * DOCUMENT_COUNT))

        result = registry.execute("development.project_document_catalog", {})

        self.assertEqual(ToolResultStatus.SUCCESS, result.status)
        self.assertEqual(DOCUMENT_COUNT, result.output["available_documents"])
        self.assertIn("readme", result.output["document_ids"])
        self.assertIn("Projektübersicht", result.output["display_names"])
        serialized = " ".join(str(value) for value in result.output.values())
        self.assertNotIn(".md", serialized)
        self.assertNotIn("/", serialized)
        self.assertNotIn("\\", serialized)

    def test_catalog_reports_missing_and_invalid_without_contents(self):
        states = ("valid", "missing", "invalid") + ("valid",) * (DOCUMENT_COUNT - 3)
        registry = self._registry(ProjectDocumentCatalogStatus(states))

        result = registry.execute("development.project_document_catalog", {})

        self.assertEqual(ToolResultStatus.SUCCESS, result.status)
        self.assertEqual(1, result.output["missing_documents"])
        self.assertEqual(1, result.output["invalid_documents"])
        self.assertNotIn("Roadmap", result.output["display_names"])
        self.assertNotIn("Qualitätsregeln", result.output["display_names"])

    def test_unknown_parameter_is_rejected_before_reader_runs(self):
        calls = []
        registry = ToolRegistry()
        register_project_document_catalog_tool(
            registry,
            status_reader=lambda _root: calls.append(True),
        )

        result = registry.execute(
            "development.project_document_catalog",
            {"path": "private.txt"},
        )

        self.assertEqual(ToolResultStatus.INVALID, result.status)
        self.assertEqual("unknown_parameter", result.error_code)
        self.assertEqual([], calls)

    def test_inconsistent_reader_result_is_safely_rejected(self):
        registry = self._registry(ProjectDocumentCatalogStatus(("valid",)))

        result = registry.execute("development.project_document_catalog", {})

        self.assertEqual(ToolResultStatus.FAILED, result.status)
        self.assertEqual("tool_execution_failed", result.error_code)
        self.assertEqual({}, dict(result.output))

    def test_reader_exception_does_not_expose_private_path(self):
        registry = ToolRegistry()

        def fail_reader(_root):
            raise OSError(r"C:\private\secret.txt")

        register_project_document_catalog_tool(registry, status_reader=fail_reader)

        result = registry.execute("development.project_document_catalog", {})

        self.assertEqual(ToolResultStatus.FAILED, result.status)
        self.assertNotIn("secret", result.message.lower())
        self.assertEqual({}, dict(result.output))

    def test_fixed_reader_accepts_only_expected_documents(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._write_fixed_documents(root)
            registry = ToolRegistry()
            register_project_document_catalog_tool(registry, root)

            result = registry.execute("development.project_document_catalog", {})

        self.assertEqual(ToolResultStatus.SUCCESS, result.status)
        self.assertEqual("complete", result.output["status"])

    @staticmethod
    def _registry(status):
        registry = ToolRegistry()
        register_project_document_catalog_tool(
            registry,
            status_reader=lambda _root: status,
        )
        return registry

    @staticmethod
    def _write_fixed_documents(root):
        documents = {
            "README.md": "# 🤖 VECTOR OFFICE AI CORE\n",
            "docs/roadmap.md": "# Roadmap\n",
            "docs/quality.md": "# Codequalität und Projektregeln\n",
            "docs/tools-security.md": "# Tool Registry und Berechtigungen\n",
            "docs/windows-startup.md": "# Windows-Autostart und Host-Watchdog\n",
            "docs/firmware-safety.md": "# Firmware-Sicherheit und kontrollierte Freigabe\n",
        }
        for relative_path, content in documents.items():
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
