"""Tests for the count-only local long-term memory status tool."""

import unittest
from unittest.mock import MagicMock

from memory.models import MemoryStatistics
from tools.memory_status import register_local_memory_status_tool
from tools.permissions import PermissionLevel
from tools.registry import ToolRegistry, ToolResultStatus


class LocalMemoryStatusToolTests(unittest.TestCase):
    def setUp(self):
        self.reader = MagicMock(return_value=MemoryStatistics(2, 1))
        self.registry = ToolRegistry()
        register_local_memory_status_tool(self.registry, self.reader)

    def test_definition_is_argument_free_and_read_only(self):
        definition = self.registry.definitions()[0]

        self.assertEqual("memory.local_status", definition.name)
        self.assertEqual(PermissionLevel.READ_ONLY, definition.permission)
        self.assertEqual((), definition.parameters)

    def test_status_returns_only_bounded_counts(self):
        result = self.registry.execute("memory.local_status", {})

        self.assertTrue(result.succeeded)
        self.assertEqual(
            {
                "memories": 2,
                "feedback": 1,
                "total_entries": 3,
                "spoken_text": (
                    "Mein lokales Gedächtnis enthält 2 bestätigte Erinnerungen "
                    "und ein bestätigtes Stil-Feedback."
                ),
            },
            dict(result.output),
        )

    def test_empty_memory_is_spoken_transparently(self):
        self.reader.return_value = MemoryStatistics(0, 0)

        result = self.registry.execute("memory.local_status", {})

        self.assertEqual(0, result.output["total_entries"])
        self.assertIn("noch keine bestätigten", result.output["spoken_text"])

    def test_parameters_are_rejected_before_memory_access(self):
        result = self.registry.execute(
            "memory.local_status",
            {"query": "private remembered text"},
        )

        self.assertEqual(ToolResultStatus.INVALID, result.status)
        self.reader.assert_not_called()

    def test_invalid_or_unbounded_status_is_sanitized(self):
        for status in (MemoryStatistics(-1, 0), "private content"):
            with self.subTest(status=status):
                self.reader.return_value = status
                result = self.registry.execute("memory.local_status", {})
                self.assertEqual(ToolResultStatus.FAILED, result.status)
                self.assertEqual({}, dict(result.output))


if __name__ == "__main__":
    unittest.main()
