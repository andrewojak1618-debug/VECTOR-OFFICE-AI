"""Tests für die sichere lokale Übersicht letzter bekannter Providerzustände."""

import unittest
from unittest.mock import MagicMock

from tools.permissions import PermissionLevel
from tools.registry import ToolRegistry, ToolResultStatus
from tools.status_overview import register_status_overview_tool


class LocalStatusOverviewToolTests(unittest.TestCase):
    def setUp(self):
        self.reader = MagicMock(return_value={
            "vector-sdk": "healthy",
            "wirepod": "healthy",
            "ollama": "healthy",
            "openai": "disabled",
            "elevenlabs": "unavailable",
        })
        self.registry = ToolRegistry()
        register_status_overview_tool(self.registry, self.reader)

    def test_definition_is_argument_free_and_read_only(self):
        definition = self.registry.definitions()[0]

        self.assertEqual("system.safe_status_overview", definition.name)
        self.assertEqual(PermissionLevel.READ_ONLY, definition.permission)
        self.assertEqual((), definition.parameters)

    def test_ready_overview_uses_only_flat_bounded_values(self):
        result = self.registry.execute("system.safe_status_overview", {})

        self.assertTrue(result.succeeded)
        self.assertEqual("ready", result.output["overall"])
        self.assertEqual("disabled", result.output["openai"])
        self.assertEqual("configured", result.output["elevenlabs"])
        self.assertEqual("not_performed", result.output["cloud_check"])
        self.assertEqual(
            "Vector ist verbunden und die lokalen Dienste sind bereit. "
            "Die Cloud wurde nicht geprüft.",
            result.output["spoken_text"],
        )
        self.assertNotIn("http", str(result.output))

    def test_unavailable_local_provider_requires_attention(self):
        self.reader.return_value["wirepod"] = "unavailable"

        result = self.registry.execute("system.safe_status_overview", {})

        self.assertEqual("attention", result.output["overall"])
        self.assertIn(
            "der lokale Sprachdienst braucht Aufmerksamkeit",
            result.output["spoken_text"],
        )

    def test_unknown_or_private_values_are_sanitized(self):
        self.reader.return_value["ollama"] = "secret host value"

        result = self.registry.execute("system.safe_status_overview", {})

        self.assertEqual("unknown", result.output["ollama"])
        self.assertEqual("limited", result.output["overall"])
        self.assertNotIn("secret host value", str(result.output))

    def test_reader_failure_returns_safe_unknown_states(self):
        self.reader.side_effect = OSError("private path")

        result = self.registry.execute("system.safe_status_overview", {})

        self.assertTrue(result.succeeded)
        self.assertEqual("limited", result.output["overall"])
        self.assertEqual("unknown", result.output["openai"])
        self.assertEqual("unknown", result.output["elevenlabs"])
        self.assertNotIn("private path", str(result.output))

    def test_multiple_local_failures_use_plural_grammar(self):
        self.reader.return_value["wirepod"] = "unavailable"
        self.reader.return_value["ollama"] = "unavailable"

        result = self.registry.execute("system.safe_status_overview", {})

        self.assertIn("brauchen Aufmerksamkeit", result.output["spoken_text"])

    def test_parameters_are_rejected_before_reading_status(self):
        result = self.registry.execute(
            "system.safe_status_overview",
            {"provider": "openai"},
        )

        self.assertEqual(ToolResultStatus.INVALID, result.status)
        self.reader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
