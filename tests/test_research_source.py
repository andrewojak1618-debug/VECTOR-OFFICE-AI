"""Tests for the fixed network-authorized research source."""

import unittest
from unittest.mock import patch

import httpx

from tools.permissions import PermissionLevel, ToolAuthorization
from tools.registry import ToolRegistry, ToolResultStatus
from tools.research_source import (
    PYTHON_SOURCE_LABEL,
    PYTHON_SOURCE_URL,
    _python_source_available,
    register_fixed_research_source_tool,
)


NETWORK_AUTHORITY = ToolAuthorization(allow_network=True, confirmed=True)


class FixedResearchSourceToolTests(unittest.TestCase):
    def setUp(self):
        self.calls = 0

        def checker():
            self.calls += 1
            return True

        self.registry = ToolRegistry()
        register_fixed_research_source_tool(self.registry, checker)

    def test_definition_is_argument_free_and_requires_network(self):
        definition = self.registry.definitions()[0]

        self.assertEqual("research.python_source_status", definition.name)
        self.assertEqual(PermissionLevel.NETWORK, definition.permission)
        self.assertEqual((), definition.parameters)

    def test_network_access_is_blocked_without_explicit_authority(self):
        result = self.registry.execute("research.python_source_status", {})

        self.assertEqual(ToolResultStatus.BLOCKED, result.status)
        self.assertEqual("network_not_allowed", result.error_code)
        self.assertEqual(0, self.calls)

    def test_network_authority_still_requires_per_call_confirmation(self):
        result = self.registry.execute(
            "research.python_source_status",
            {},
            ToolAuthorization(allow_network=True),
        )

        self.assertEqual(ToolResultStatus.BLOCKED, result.status)
        self.assertEqual("network_confirmation_required", result.error_code)
        self.assertEqual(0, self.calls)

    def test_confirmed_network_request_returns_bounded_source_status(self):
        result = self.registry.execute(
            "research.python_source_status",
            {},
            NETWORK_AUTHORITY,
        )

        self.assertTrue(result.succeeded)
        self.assertEqual(
            {"source", "available", "status", "spoken_text"},
            set(result.output),
        )
        self.assertEqual(PYTHON_SOURCE_LABEL, result.output["source"])
        self.assertTrue(result.output["available"])
        self.assertEqual(1, self.calls)

    def test_parameters_are_rejected_before_network_check(self):
        result = self.registry.execute(
            "research.python_source_status",
            {"url": "https://example.com"},
            NETWORK_AUTHORITY,
        )

        self.assertEqual(ToolResultStatus.INVALID, result.status)
        self.assertEqual(0, self.calls)

    def test_unavailable_source_is_a_safe_status_not_an_exception(self):
        registry = ToolRegistry()
        register_fixed_research_source_tool(registry, lambda: False)

        result = registry.execute(
            "research.python_source_status",
            {},
            NETWORK_AUTHORITY,
        )

        self.assertTrue(result.succeeded)
        self.assertEqual("unavailable", result.output["status"])
        self.assertNotIn("http", result.output["spoken_text"])

    def test_invalid_checker_result_is_sanitized(self):
        registry = ToolRegistry()
        register_fixed_research_source_tool(registry, lambda: "yes")

        result = registry.execute(
            "research.python_source_status",
            {},
            NETWORK_AUTHORITY,
        )

        self.assertEqual(ToolResultStatus.FAILED, result.status)
        self.assertEqual({}, dict(result.output))

    @patch("tools.research_source.httpx.head")
    def test_default_check_uses_only_fixed_url_without_redirects(self, head):
        head.return_value = httpx.Response(200)

        self.assertTrue(_python_source_available())

        arguments, options = head.call_args
        self.assertEqual((PYTHON_SOURCE_URL,), arguments)
        self.assertFalse(options["follow_redirects"])
        self.assertGreater(options["timeout"], 0)
        self.assertEqual({"User-Agent"}, set(options["headers"]))

    @patch("tools.research_source.httpx.head")
    def test_transport_error_exposes_no_details(self, head):
        head.side_effect = httpx.ConnectError("private network detail")

        self.assertFalse(_python_source_available())


if __name__ == "__main__":
    unittest.main()
