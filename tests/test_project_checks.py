"""Tests for the confirmed fixed local project test tool."""

import unittest
from pathlib import Path

from tools.permissions import PermissionLevel, ToolAuthorization
from tools.project_checks import (
    CoreProjectTestTool,
    CoreTestSummary,
    register_core_project_test_tool,
)
from tools.registry import ToolRegistry, ToolResultStatus


class CoreProjectTestToolTests(unittest.TestCase):
    def setUp(self):
        self.calls = 0
        self.registry = ToolRegistry()
        register_core_project_test_tool(
            self.registry,
            Path("."),
            Path("python.exe"),
            self._successful_run,
        )

    def _successful_run(self, _project_root, _python_executable):
        self.calls += 1
        return CoreTestSummary(True, 449, 4.12)

    def test_definition_is_argument_free_and_mutating(self):
        definition = self.registry.definitions()[0]

        self.assertEqual("development.run_core_tests", definition.name)
        self.assertEqual(PermissionLevel.MUTATING, definition.permission)
        self.assertEqual((), definition.parameters)

    def test_execution_is_blocked_without_mutation_authority(self):
        result = self.registry.execute("development.run_core_tests", {})

        self.assertEqual(ToolResultStatus.BLOCKED, result.status)
        self.assertEqual(0, self.calls)

    def test_confirmed_execution_returns_only_bounded_summary(self):
        result = self.registry.execute(
            "development.run_core_tests",
            {},
            ToolAuthorization(allow_mutation=True, confirmed=True),
        )

        self.assertTrue(result.succeeded)
        self.assertEqual(1, self.calls)
        self.assertEqual(
            {"passed", "test_count", "duration_seconds", "spoken_text"},
            set(result.output),
        )
        self.assertEqual(449, result.output["test_count"])
        self.assertEqual(4.12, result.output["duration_seconds"])
        self.assertIn(
            "400 Tests und weitere 49 Tests",
            result.output["spoken_text"],
        )
        self.assertNotIn("stdout", result.output)
        self.assertNotIn("stderr", result.output)

    def test_failed_suite_is_reported_without_raw_output(self):
        registry = ToolRegistry()
        register_core_project_test_tool(
            registry,
            Path("."),
            Path("python.exe"),
            lambda _root, _python: CoreTestSummary(False, 449, 4.0),
        )

        result = registry.execute(
            "development.run_core_tests",
            {},
            ToolAuthorization(allow_mutation=True, confirmed=True),
        )

        self.assertTrue(result.succeeded)
        self.assertFalse(result.output["passed"])
        self.assertIn("fehlgeschlagen", result.output["spoken_text"])

    def test_parameters_are_rejected_before_runner_execution(self):
        result = self.registry.execute(
            "development.run_core_tests",
            {"command": "private"},
            ToolAuthorization(allow_mutation=True, confirmed=True),
        )

        self.assertEqual(ToolResultStatus.INVALID, result.status)
        self.assertEqual(0, self.calls)

    def test_invalid_runner_result_is_sanitized_by_registry(self):
        tool = CoreProjectTestTool(
            Path("."),
            Path("python.exe"),
            lambda _root, _python: "private output",
        )
        registry = ToolRegistry()
        registry.register(tool)

        result = registry.execute(
            "development.run_core_tests",
            {},
            ToolAuthorization(allow_mutation=True, confirmed=True),
        )

        self.assertEqual(ToolResultStatus.FAILED, result.status)
        self.assertEqual({}, dict(result.output))

    def test_summary_rejects_invalid_counts_and_duration(self):
        with self.assertRaises(ValueError):
            CoreTestSummary(True, -1, 1.0)
        with self.assertRaises(ValueError):
            CoreTestSummary(True, 1, float("inf"))


if __name__ == "__main__":
    unittest.main()
