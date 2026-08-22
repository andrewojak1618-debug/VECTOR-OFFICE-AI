"""Tests for bounded local Python quality metrics."""

import unittest
from pathlib import Path

from tools.code_quality_status import (
    CodeQualityStatus,
    LocalCodeQualityStatusTool,
    _spoken_number,
    inspect_code_quality,
    register_code_quality_status_tool,
)
from tools.permissions import PermissionLevel
from tools.registry import ToolRegistry, ToolResultStatus


CLEAN_STATUS = CodeQualityStatus(90, 763, 0, 0, 0, 0, 0)


class LocalCodeQualityStatusToolTests(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()
        register_code_quality_status_tool(
            self.registry,
            Path("."),
            lambda _root: CLEAN_STATUS,
        )

    def test_definition_is_argument_free_and_read_only(self):
        definition = self.registry.definitions()[0]

        self.assertEqual("development.code_quality_status", definition.name)
        self.assertEqual(PermissionLevel.READ_ONLY, definition.permission)
        self.assertEqual((), definition.parameters)

    def test_clean_output_contains_only_counts_and_local_summary(self):
        result = self.registry.execute("development.code_quality_status", {})

        self.assertTrue(result.succeeded)
        self.assertEqual("clean", result.output["status"])
        self.assertEqual(0, result.output["issue_count"])
        self.assertIn("neunzig Module", result.output["spoken_text"])
        self.assertNotIn(".py", result.output["spoken_text"])

    def test_spoken_numbers_use_clear_german_words(self):
        values = (0, 1, 19, 20, 21, 90, 91, 778, 1_000, 100_000)
        expected = (
            "null", "eins", "neunzehn", "zwanzig", "einundzwanzig",
            "neunzig", "einundneunzig", "siebenhundertachtundsiebzig",
            "eintausend", "einhunderttausend",
        )

        self.assertEqual(expected, tuple(_spoken_number(value) for value in values))

    def test_issue_output_exposes_counts_without_source_details(self):
        registry = ToolRegistry()
        register_code_quality_status_tool(
            registry,
            Path("."),
            lambda _root: CodeQualityStatus(90, 763, 1, 2, 3, 4, 5),
        )

        result = registry.execute("development.code_quality_status", {})

        self.assertEqual("issues", result.output["status"])
        self.assertEqual(15, result.output["issue_count"])
        self.assertIn("Eine fehlende Modulbeschreibung", result.output["spoken_text"])
        self.assertNotIn("tools/", result.output["spoken_text"])

    def test_parameters_are_rejected_before_reading(self):
        reader_called = False

        def reader(_root):
            nonlocal reader_called
            reader_called = True
            return CLEAN_STATUS

        registry = ToolRegistry()
        register_code_quality_status_tool(registry, Path("."), reader)

        result = registry.execute(
            "development.code_quality_status",
            {"path": "private.py"},
        )

        self.assertEqual(ToolResultStatus.INVALID, result.status)
        self.assertFalse(reader_called)

    def test_inconsistent_counts_are_rejected_and_sanitized(self):
        registry = ToolRegistry()
        register_code_quality_status_tool(
            registry,
            Path("."),
            lambda _root: CodeQualityStatus(1, 1, 2, 0, 0, 0, 0),
        )

        result = registry.execute("development.code_quality_status", {})

        self.assertEqual(ToolResultStatus.FAILED, result.status)
        self.assertEqual({}, dict(result.output))

    def test_reader_error_is_sanitized_by_registry(self):
        registry = ToolRegistry()
        registry.register(LocalCodeQualityStatusTool(
            Path("."),
            self._raise_reader_error,
        ))

        result = registry.execute("development.code_quality_status", {})

        self.assertEqual(ToolResultStatus.FAILED, result.status)
        self.assertEqual({}, dict(result.output))

    def test_real_project_inspection_reports_clean_rules(self):
        status = inspect_code_quality()

        self.assertGreater(status.modules, 0)
        self.assertGreater(status.functions, 0)
        self.assertEqual(0, status.issue_count)

    @staticmethod
    def _raise_reader_error(_root):
        raise OSError("private local path")


if __name__ == "__main__":
    unittest.main()
