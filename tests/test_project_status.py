"""Tests for the bounded local project status development tool."""

import unittest
from pathlib import Path

from tools.permissions import PermissionLevel
from tools.project_status import (
    ProjectGitMetadata,
    ProjectStatusTool,
    register_project_status_tool,
)
from tools.registry import ToolRegistry, ToolResultStatus


TEST_METADATA = ProjectGitMetadata("main", "f04652f", 2)


class ProjectStatusToolTests(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()
        register_project_status_tool(
            self.registry,
            Path("."),
            lambda _root: TEST_METADATA,
            lambda _root: True,
        )

    def test_definition_is_argument_free_and_read_only(self):
        definition = self.registry.definitions()[0]

        self.assertEqual("development.project_status", definition.name)
        self.assertEqual(PermissionLevel.READ_ONLY, definition.permission)
        self.assertEqual((), definition.parameters)

    def test_status_contains_only_sanitized_metadata(self):
        result = self.registry.execute("development.project_status", {})

        self.assertTrue(result.succeeded)
        self.assertEqual(
            {
                "branch",
                "commit",
                "open_changes",
                "acceptance_status",
                "spoken_text",
            },
            set(result.output),
        )
        self.assertEqual("main", result.output["branch"])
        self.assertEqual("f04652f", result.output["commit"])
        self.assertEqual(2, result.output["open_changes"])
        self.assertEqual("passed", result.output["acceptance_status"])

    def test_unknown_acceptance_status_is_spoken_transparently(self):
        registry = ToolRegistry()
        register_project_status_tool(
            registry,
            Path("."),
            lambda _root: TEST_METADATA,
            lambda _root: None,
        )

        result = registry.execute("development.project_status", {})

        self.assertEqual("unknown", result.output["acceptance_status"])
        self.assertIn("kein sicherer Status", result.output["spoken_text"])

    def test_parameters_are_rejected_before_execution(self):
        result = self.registry.execute(
            "development.project_status",
            {"path": "private.txt"},
        )

        self.assertEqual(ToolResultStatus.INVALID, result.status)

    def test_reader_failure_is_sanitized_by_registry(self):
        tool = ProjectStatusTool(
            Path("."),
            lambda _root: self._raise_reader_error(),
            lambda _root: True,
        )
        registry = ToolRegistry()
        registry.register(tool)

        result = registry.execute("development.project_status", {})

        self.assertEqual(ToolResultStatus.FAILED, result.status)
        self.assertEqual({}, dict(result.output))

    @staticmethod
    def _raise_reader_error():
        raise OSError("private local path")

    def test_metadata_rejects_unsafe_branch_and_commit_values(self):
        with self.assertRaises(ValueError):
            ProjectGitMetadata("main\nsecret", "f04652f", 0)
        with self.assertRaises(ValueError):
            ProjectGitMetadata("main", "not-a-hash", 0)


if __name__ == "__main__":
    unittest.main()
