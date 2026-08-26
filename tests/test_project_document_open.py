"""Tests for confirmed opening of fixed approved project documents."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tools.permissions import PermissionLevel, ToolAuthorization
from tools.project_documents import register_project_document_open_tool
from tools.registry import ToolRegistry
from tools.registry_types import ToolResultStatus
from tools.tool_values import ToolParameterType


TOOL_NAME = "development.open_project_document"


class ProjectDocumentOpenToolTests(unittest.TestCase):
    def test_definition_requires_one_fixed_identifier_and_mutation_right(self):
        registry = ToolRegistry()
        register_project_document_open_tool(registry, opener=MagicMock())
        definition = registry.definitions()[0]

        self.assertEqual(TOOL_NAME, definition.name)
        self.assertEqual(PermissionLevel.MUTATING, definition.permission)
        self.assertEqual(1, len(definition.parameters))
        self.assertEqual("document_id", definition.parameters[0].name)
        self.assertEqual(ToolParameterType.STRING, definition.parameters[0].parameter_type)

    def test_opening_is_blocked_without_explicit_mutation_authority(self):
        opener = MagicMock()
        registry = ToolRegistry()
        register_project_document_open_tool(registry, opener=opener)

        result = registry.execute(TOOL_NAME, {"document_id": "readme"})

        self.assertEqual(ToolResultStatus.BLOCKED, result.status)
        opener.assert_not_called()

    def test_confirmed_fixed_document_opens_only_resolved_allowlisted_path(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "README.md").write_text(
                "# 🤖 VECTOR OFFICE AI CORE\n",
                encoding="utf-8",
            )
            opener = MagicMock()
            registry = ToolRegistry()
            register_project_document_open_tool(registry, root, opener)

            result = registry.execute(
                TOOL_NAME,
                {"document_id": "readme"},
                ToolAuthorization(allow_mutation=True, confirmed=True),
            )

        self.assertEqual(ToolResultStatus.SUCCESS, result.status)
        opener.assert_called_once_with((root / "README.md").resolve())
        self.assertEqual("readme", result.output["document_id"])
        self.assertEqual("Projektübersicht", result.output["display_name"])
        serialized = " ".join(str(value) for value in result.output.values())
        self.assertNotIn(".md", serialized)
        self.assertNotIn(str(root), serialized)

    def test_unknown_document_identifier_is_safely_rejected(self):
        opener = MagicMock()
        registry = ToolRegistry()
        register_project_document_open_tool(registry, opener=opener)

        result = registry.execute(
            TOOL_NAME,
            {"document_id": "../../private"},
            ToolAuthorization(allow_mutation=True, confirmed=True),
        )

        self.assertEqual(ToolResultStatus.FAILED, result.status)
        self.assertEqual("tool_execution_failed", result.error_code)
        self.assertNotIn("private", result.message)
        opener.assert_not_called()

    def test_free_path_parameter_is_rejected_before_opening(self):
        opener = MagicMock()
        registry = ToolRegistry()
        register_project_document_open_tool(registry, opener=opener)

        result = registry.execute(
            TOOL_NAME,
            {"document_id": "readme", "path": r"C:\private.txt"},
            ToolAuthorization(allow_mutation=True, confirmed=True),
        )

        self.assertEqual(ToolResultStatus.INVALID, result.status)
        self.assertEqual("unknown_parameter", result.error_code)
        opener.assert_not_called()

    def test_missing_or_invalid_document_is_never_opened(self):
        for content in (None, "# Fremdes Dokument\n"):
            with self.subTest(content=content):
                self._assert_unavailable_document_is_not_opened(content)

    def test_opener_failure_is_sanitized_without_path_output(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "README.md").write_text(
                "# 🤖 VECTOR OFFICE AI CORE\n",
                encoding="utf-8",
            )
            registry = ToolRegistry()
            register_project_document_open_tool(
                registry,
                root,
                lambda path: (_ for _ in ()).throw(OSError(str(path))),
            )

            result = registry.execute(
                TOOL_NAME,
                {"document_id": "readme"},
                ToolAuthorization(allow_mutation=True, confirmed=True),
            )

        self.assertEqual(ToolResultStatus.FAILED, result.status)
        self.assertEqual({}, dict(result.output))
        self.assertNotIn(str(root), result.message)

    @staticmethod
    def _assert_unavailable_document_is_not_opened(content):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            if content is not None:
                (root / "README.md").write_text(content, encoding="utf-8")
            opener = MagicMock()
            registry = ToolRegistry()
            register_project_document_open_tool(registry, root, opener)
            result = registry.execute(
                TOOL_NAME,
                {"document_id": "readme"},
                ToolAuthorization(allow_mutation=True, confirmed=True),
            )
        if result.status is not ToolResultStatus.FAILED:
            raise AssertionError("Unavailable document must fail safely.")
        opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
