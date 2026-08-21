"""Tests for the fixed local next-roadmap-item tool."""

import tempfile
import unittest
from pathlib import Path

from tools.permissions import PermissionLevel
from tools.registry import ToolRegistry, ToolResultStatus
from tools.roadmap_status import (
    NextRoadmapItemTool,
    register_next_roadmap_item_tool,
)


NEXT_ITEM = "kontrollierten lokalen Dokumentationsstatus ergänzen"


class NextRoadmapItemToolTests(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()
        register_next_roadmap_item_tool(
            self.registry,
            Path("."),
            lambda _root: NEXT_ITEM,
        )

    def test_definition_is_argument_free_and_read_only(self):
        definition = self.registry.definitions()[0]

        self.assertEqual("development.next_roadmap_item", definition.name)
        self.assertEqual(PermissionLevel.READ_ONLY, definition.permission)
        self.assertEqual((), definition.parameters)

    def test_output_contains_only_bounded_status_fields(self):
        result = self.registry.execute("development.next_roadmap_item", {})

        self.assertTrue(result.succeeded)
        self.assertEqual(
            {"found", "next_item", "spoken_text"},
            set(result.output),
        )
        self.assertTrue(result.output["found"])
        self.assertEqual(NEXT_ITEM, result.output["next_item"])
        self.assertIn(NEXT_ITEM, result.output["spoken_text"])

    def test_reader_uses_only_first_pending_item_in_fixed_section(self):
        content = """# Roadmap

## Other
- ⏳ falscher Punkt

## Tools und Sicherheit
- ✅ erledigt
- ⏳ erster sicherer Punkt
- ⏳ zweiter sicherer Punkt

## Next
- ⏳ späterer Punkt
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / "docs"
            docs.mkdir()
            (docs / "roadmap.md").write_text(content, encoding="utf-8")
            registry = ToolRegistry()
            register_next_roadmap_item_tool(registry, root)

            result = registry.execute("development.next_roadmap_item", {})

        self.assertEqual("erster sicherer Punkt", result.output["next_item"])

    def test_empty_section_is_reported_transparently(self):
        registry = ToolRegistry()
        register_next_roadmap_item_tool(registry, Path("."), lambda _root: None)

        result = registry.execute("development.next_roadmap_item", {})

        self.assertFalse(result.output["found"])
        self.assertEqual("", result.output["next_item"])
        self.assertIn("kein offener Punkt", result.output["spoken_text"])

    def test_parameters_are_rejected_before_reading(self):
        reader_called = False

        def reader(_root):
            nonlocal reader_called
            reader_called = True
            return NEXT_ITEM

        registry = ToolRegistry()
        register_next_roadmap_item_tool(registry, Path("."), reader)

        result = registry.execute(
            "development.next_roadmap_item",
            {"path": "private.txt"},
        )

        self.assertEqual(ToolResultStatus.INVALID, result.status)
        self.assertFalse(reader_called)

    def test_unsafe_reader_content_is_rejected_and_sanitized(self):
        registry = ToolRegistry()
        register_next_roadmap_item_tool(
            registry,
            Path("."),
            lambda _root: "https://private.example/secret",
        )

        result = registry.execute("development.next_roadmap_item", {})

        self.assertEqual(ToolResultStatus.FAILED, result.status)
        self.assertEqual({}, dict(result.output))

    def test_reader_error_is_sanitized_by_registry(self):
        tool = NextRoadmapItemTool(Path("."), self._raise_reader_error)
        registry = ToolRegistry()
        registry.register(tool)

        result = registry.execute("development.next_roadmap_item", {})

        self.assertEqual(ToolResultStatus.FAILED, result.status)
        self.assertEqual({}, dict(result.output))

    @staticmethod
    def _raise_reader_error(_root):
        raise OSError("private local path")


if __name__ == "__main__":
    unittest.main()
