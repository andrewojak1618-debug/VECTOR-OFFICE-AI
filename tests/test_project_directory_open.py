"""Tests für das bestätigte Öffnen eines fest freigegebenen Projektordners."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tools.permissions import PermissionLevel, ToolAuthorization
from tools.project_directories import register_project_directory_open_tool
from tools.registry import ToolRegistry
from tools.registry_types import ToolResultStatus
from tools.tool_values import ToolParameterType


TOOL_NAME = "development.open_project_directory"


class ProjectDirectoryOpenToolTests(unittest.TestCase):
    def test_definition_requires_fixed_identifier_and_mutation_right(self):
        registry = ToolRegistry()
        register_project_directory_open_tool(registry, opener=MagicMock())
        definition = registry.definitions()[0]

        self.assertEqual(TOOL_NAME, definition.name)
        self.assertEqual(PermissionLevel.MUTATING, definition.permission)
        self.assertEqual(1, len(definition.parameters))
        self.assertEqual("directory_id", definition.parameters[0].name)
        self.assertEqual(ToolParameterType.STRING, definition.parameters[0].parameter_type)

    def test_opening_is_blocked_without_explicit_mutation_authority(self):
        opener = MagicMock()
        registry = ToolRegistry()
        register_project_directory_open_tool(registry, opener=opener)

        result = registry.execute(TOOL_NAME, {"directory_id": "documentation"})

        self.assertEqual(ToolResultStatus.BLOCKED, result.status)
        opener.assert_not_called()

    def test_confirmed_fixed_directory_opens_only_allowlisted_path(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            opener = MagicMock()
            registry = ToolRegistry()
            register_project_directory_open_tool(registry, root, opener)

            result = registry.execute(
                TOOL_NAME,
                {"directory_id": "documentation"},
                ToolAuthorization(allow_mutation=True, confirmed=True),
            )

        self.assertEqual(ToolResultStatus.SUCCESS, result.status)
        opener.assert_called_once_with((root / "docs").resolve())
        self.assertEqual("documentation", result.output["directory_id"])
        self.assertNotIn(str(root), " ".join(map(str, result.output.values())))

    def test_unknown_identifier_and_free_path_are_rejected(self):
        for arguments in (
            {"directory_id": "../../private"},
            {"directory_id": "documentation", "path": r"C:\private"},
        ):
            with self.subTest(arguments=arguments):
                opener = MagicMock()
                registry = ToolRegistry()
                register_project_directory_open_tool(registry, opener=opener)

                result = registry.execute(
                    TOOL_NAME,
                    arguments,
                    ToolAuthorization(allow_mutation=True, confirmed=True),
                )

                self.assertIn(
                    result.status,
                    {ToolResultStatus.FAILED, ToolResultStatus.INVALID},
                )
                opener.assert_not_called()

    def test_missing_or_file_replacement_is_never_opened(self):
        for create_file in (False, True):
            with self.subTest(create_file=create_file):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    root = Path(temporary_directory)
                    if create_file:
                        (root / "docs").write_text("kein Ordner", encoding="utf-8")
                    opener = MagicMock()
                    registry = ToolRegistry()
                    register_project_directory_open_tool(registry, root, opener)
                    result = registry.execute(
                        TOOL_NAME,
                        {"directory_id": "documentation"},
                        ToolAuthorization(allow_mutation=True, confirmed=True),
                    )

                self.assertEqual(ToolResultStatus.FAILED, result.status)
                opener.assert_not_called()

    def test_opener_failure_is_sanitized_without_path_output(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "docs").mkdir()
            registry = ToolRegistry()
            register_project_directory_open_tool(
                registry,
                root,
                MagicMock(side_effect=OSError(str(root))),
            )
            result = registry.execute(
                TOOL_NAME,
                {"directory_id": "documentation"},
                ToolAuthorization(allow_mutation=True, confirmed=True),
            )

        self.assertEqual(ToolResultStatus.FAILED, result.status)
        self.assertEqual("tool_execution_failed", result.error_code)
        self.assertNotIn(str(root), result.message)


if __name__ == "__main__":
    unittest.main()
