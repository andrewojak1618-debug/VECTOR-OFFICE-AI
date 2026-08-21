"""Tests for count-only health of fixed project documentation."""

import tempfile
import unittest
from pathlib import Path

from tools.documentation_status import (
    DOCUMENT_COUNT,
    REQUIRED_DOCUMENTS,
    DocumentationStatus,
    LocalDocumentationStatusTool,
    register_documentation_status_tool,
)
from tools.permissions import PermissionLevel
from tools.registry import ToolRegistry, ToolResultStatus


class LocalDocumentationStatusToolTests(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()
        register_documentation_status_tool(
            self.registry,
            Path("."),
            lambda _root: DocumentationStatus(DOCUMENT_COUNT, 0, 0),
        )

    def test_definition_is_argument_free_and_read_only(self):
        definition = self.registry.definitions()[0]

        self.assertEqual("development.documentation_status", definition.name)
        self.assertEqual(PermissionLevel.READ_ONLY, definition.permission)
        self.assertEqual((), definition.parameters)

    def test_complete_output_contains_only_counts_and_local_summary(self):
        result = self.registry.execute("development.documentation_status", {})

        self.assertTrue(result.succeeded)
        self.assertEqual(
            {
                "total_documents",
                "valid_documents",
                "missing_documents",
                "invalid_documents",
                "status",
                "spoken_text",
            },
            set(result.output),
        )
        self.assertEqual("complete", result.output["status"])
        self.assertIn("vollständig", result.output["spoken_text"])

    def test_fixed_reader_counts_missing_and_invalid_without_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative_path, heading in REQUIRED_DOCUMENTS:
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"{heading}\n", encoding="utf-8")
            (root / REQUIRED_DOCUMENTS[0][0]).unlink()
            (root / REQUIRED_DOCUMENTS[1][0]).write_text(
                "# Falsche Überschrift\n",
                encoding="utf-8",
            )
            registry = ToolRegistry()
            register_documentation_status_tool(registry, root)

            result = registry.execute("development.documentation_status", {})

        self.assertEqual(DOCUMENT_COUNT - 2, result.output["valid_documents"])
        self.assertEqual(1, result.output["missing_documents"])
        self.assertEqual(1, result.output["invalid_documents"])
        self.assertNotIn("README", result.output["spoken_text"])
        self.assertNotIn("CHANGELOG", result.output["spoken_text"])

    def test_incomplete_status_uses_correct_singular_grammar(self):
        registry = ToolRegistry()
        register_documentation_status_tool(
            registry,
            Path("."),
            lambda _root: DocumentationStatus(DOCUMENT_COUNT - 2, 1, 1),
        )

        result = registry.execute("development.documentation_status", {})

        self.assertEqual("incomplete", result.output["status"])
        self.assertIn("1 Dokument fehlt", result.output["spoken_text"])
        self.assertIn("1 Dokument ist ungültig", result.output["spoken_text"])

    def test_parameters_are_rejected_before_reading(self):
        reader_called = False

        def reader(_root):
            nonlocal reader_called
            reader_called = True
            return DocumentationStatus(DOCUMENT_COUNT, 0, 0)

        registry = ToolRegistry()
        register_documentation_status_tool(registry, Path("."), reader)

        result = registry.execute(
            "development.documentation_status",
            {"path": "private.md"},
        )

        self.assertEqual(ToolResultStatus.INVALID, result.status)
        self.assertFalse(reader_called)

    def test_inconsistent_counts_are_rejected_and_sanitized(self):
        registry = ToolRegistry()
        register_documentation_status_tool(
            registry,
            Path("."),
            lambda _root: DocumentationStatus(DOCUMENT_COUNT, 1, 0),
        )

        result = registry.execute("development.documentation_status", {})

        self.assertEqual(ToolResultStatus.FAILED, result.status)
        self.assertEqual({}, dict(result.output))

    def test_reader_error_is_sanitized_by_registry(self):
        registry = ToolRegistry()
        registry.register(LocalDocumentationStatusTool(
            Path("."),
            self._raise_reader_error,
        ))

        result = registry.execute("development.documentation_status", {})

        self.assertEqual(ToolResultStatus.FAILED, result.status)
        self.assertEqual({}, dict(result.output))

    @staticmethod
    def _raise_reader_error(_root):
        raise OSError("private local path")


if __name__ == "__main__":
    unittest.main()
