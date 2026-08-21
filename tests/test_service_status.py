"""Tests for the bounded local runtime service status tool."""

import unittest
from unittest.mock import MagicMock

from tools.permissions import PermissionLevel
from tools.registry import ToolRegistry, ToolResultStatus
from tools.service_status import register_local_service_status_tool


class LocalServiceStatusToolTests(unittest.TestCase):
    def setUp(self):
        self.wirepod = MagicMock(return_value=True)
        self.ollama = MagicMock(return_value=True)
        self.registry = ToolRegistry()
        register_local_service_status_tool(
            self.registry,
            self.wirepod,
            self.ollama,
        )

    def test_definition_is_argument_free_and_read_only(self):
        definition = self.registry.definitions()[0]

        self.assertEqual("system.local_service_status", definition.name)
        self.assertEqual(PermissionLevel.READ_ONLY, definition.permission)
        self.assertEqual((), definition.parameters)

    def test_available_services_return_only_bounded_states(self):
        result = self.registry.execute("system.local_service_status", {})

        self.assertTrue(result.succeeded)
        self.assertEqual(
            {
                "application",
                "wirepod",
                "ollama",
                "all_available",
                "spoken_text",
            },
            set(result.output),
        )
        self.assertTrue(result.output["all_available"])
        self.assertIn("WirePod ist lokal verfügbar", result.output["spoken_text"])
        self.assertNotIn("http", str(result.output))

    def test_unavailable_service_is_reported_without_exception_details(self):
        self.wirepod.side_effect = OSError("private host detail")

        result = self.registry.execute("system.local_service_status", {})

        self.assertTrue(result.succeeded)
        self.assertFalse(result.output["wirepod"])
        self.assertTrue(result.output["ollama"])
        self.assertNotIn("private host detail", str(result.output))

    def test_parameters_are_rejected_before_health_checks(self):
        result = self.registry.execute(
            "system.local_service_status",
            {"host": "https://example.invalid"},
        )

        self.assertEqual(ToolResultStatus.INVALID, result.status)
        self.wirepod.assert_not_called()
        self.ollama.assert_not_called()

    def test_invalid_checker_result_is_sanitized_by_registry(self):
        self.ollama.return_value = "online"

        result = self.registry.execute("system.local_service_status", {})

        self.assertEqual(ToolResultStatus.FAILED, result.status)
        self.assertEqual({}, dict(result.output))


if __name__ == "__main__":
    unittest.main()
