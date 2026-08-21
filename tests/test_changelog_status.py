"""Tests for the fixed local latest-changelog tool."""

import tempfile
import unittest
from pathlib import Path

from tools.changelog_status import (
    LatestProjectChangeTool,
    register_latest_project_change_tool,
)
from tools.permissions import PermissionLevel
from tools.registry import ToolRegistry, ToolResultStatus


class LatestProjectChangeToolTests(unittest.TestCase):
    def setUp(self):
        self.reader_calls = 0

        def reader(_root):
            self.reader_calls += 1
            return "kontrolliertes Werkzeug ergänzt"

        self.registry = ToolRegistry()
        register_latest_project_change_tool(self.registry, Path("."), reader)

    def test_definition_is_argument_free_and_read_only(self):
        definition = self.registry.definitions()[0]

        self.assertEqual("development.latest_change", definition.name)
        self.assertEqual(PermissionLevel.READ_ONLY, definition.permission)
        self.assertEqual((), definition.parameters)

    def test_output_contains_only_bounded_public_summary(self):
        result = self.registry.execute("development.latest_change", {})

        self.assertTrue(result.succeeded)
        self.assertEqual({"found", "summary", "spoken_text"}, set(result.output))
        self.assertEqual("kontrolliertes Werkzeug ergänzt", result.output["summary"])
        self.assertEqual(1, self.reader_calls)

    def test_fixed_reader_uses_first_unreleased_entry_and_strips_markup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "CHANGELOG.md").write_text(
                "# Changelog\n\n## [Unreleased]\n\n"
                "- `development.latest_change` sicher ergänzt\n"
                "- zweiter Eintrag\n\n## [0.1.0]\n- alt\n",
                encoding="utf-8",
            )
            registry = ToolRegistry()
            register_latest_project_change_tool(registry, root)

            result = registry.execute("development.latest_change", {})

        self.assertTrue(result.succeeded)
        self.assertEqual(
            "development.latest_change sicher ergänzt",
            result.output["summary"],
        )
        self.assertNotIn("zweiter Eintrag", result.output["spoken_text"])

    def test_empty_unreleased_section_returns_transparent_absence(self):
        registry = ToolRegistry()
        register_latest_project_change_tool(registry, Path("."), lambda _root: None)

        result = registry.execute("development.latest_change", {})

        self.assertTrue(result.succeeded)
        self.assertFalse(result.output["found"])
        self.assertEqual("", result.output["summary"])

    def test_parameters_are_rejected_before_file_read(self):
        result = self.registry.execute(
            "development.latest_change",
            {"path": "private.txt"},
        )

        self.assertEqual(ToolResultStatus.INVALID, result.status)
        self.assertEqual(0, self.reader_calls)

    def test_url_or_path_like_summary_is_rejected(self):
        for unsafe in ("siehe https://example.com", "siehe private/datei"):
            registry = ToolRegistry()
            register_latest_project_change_tool(
                registry,
                Path("."),
                lambda _root, value=unsafe: value,
            )

            result = registry.execute("development.latest_change", {})

            self.assertEqual(ToolResultStatus.FAILED, result.status)
            self.assertEqual({}, dict(result.output))

    def test_reader_error_is_sanitized_by_registry(self):
        registry = ToolRegistry()
        registry.register(LatestProjectChangeTool(Path("."), self._raise_error))

        result = registry.execute("development.latest_change", {})

        self.assertEqual(ToolResultStatus.FAILED, result.status)
        self.assertEqual({}, dict(result.output))

    @staticmethod
    def _raise_error(_root):
        raise OSError("private local path")


if __name__ == "__main__":
    unittest.main()
