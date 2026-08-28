"""Tests für das bestätigte lokale Memory-Schreibwerkzeug."""

import unittest
from unittest.mock import MagicMock

from memory.models import MemoryEntry
from tools.memory_write import (
    MAX_MEMORY_CONTENT_LENGTH,
    register_confirmed_memory_write_tool,
)
from tools.permissions import PermissionLevel, ToolAuthorization
from tools.registry import REDACTED_ARGUMENT, ToolRegistry, ToolResultStatus


def memory_entry(content: str) -> MemoryEntry:
    return MemoryEntry(7, content, "fact", "user-confirmed-voice", "now")


class ConfirmedMemoryWriteToolTests(unittest.TestCase):
    def setUp(self):
        self.writer = MagicMock(side_effect=lambda content, **_values: memory_entry(content))
        self.audit = MagicMock()
        self.registry = ToolRegistry(audit_sink=self.audit)
        register_confirmed_memory_write_tool(self.registry, self.writer)

    def test_definition_marks_content_sensitive_and_mutating(self):
        definition = self.registry.definitions()[0]

        self.assertEqual("memory.remember_confirmed", definition.name)
        self.assertEqual(PermissionLevel.MUTATING, definition.permission)
        self.assertTrue(definition.parameters[0].sensitive)

    def test_missing_authority_blocks_before_storage(self):
        result = self.registry.execute(
            "memory.remember_confirmed",
            {"content": "Vector spricht Deutsch."},
        )

        self.assertEqual(ToolResultStatus.BLOCKED, result.status)
        self.writer.assert_not_called()

    def test_confirmed_content_is_stored_once_without_content_output(self):
        result = self.registry.execute(
            "memory.remember_confirmed",
            {"content": "  Vector spricht   Deutsch.  "},
            ToolAuthorization(allow_mutation=True, confirmed=True),
        )

        self.assertTrue(result.succeeded)
        self.writer.assert_called_once_with(
            "Vector spricht Deutsch.",
            category="fact",
            source="user-confirmed-voice",
        )
        self.assertNotIn("Vector spricht", str(dict(result.output)))
        self.assertEqual(True, result.output["stored"])

    def test_audit_redacts_memory_content(self):
        self.registry.execute(
            "memory.remember_confirmed",
            {"content": "Diese Information ist privat."},
            ToolAuthorization(allow_mutation=True, confirmed=True),
        )

        event = self.audit.call_args.args[0]
        self.assertEqual(REDACTED_ARGUMENT, event.arguments["content"])
        self.assertNotIn("privat", str(event))

    def test_empty_multiline_and_long_content_fail_safely(self):
        for content in ("", "Zeile eins\nZeile zwei", "x" * (MAX_MEMORY_CONTENT_LENGTH + 1)):
            with self.subTest(content_length=len(content)):
                result = self.registry.execute(
                    "memory.remember_confirmed",
                    {"content": content},
                    ToolAuthorization(allow_mutation=True, confirmed=True),
                )
                self.assertEqual(ToolResultStatus.FAILED, result.status)
                self.assertEqual({}, dict(result.output))


if __name__ == "__main__":
    unittest.main()
