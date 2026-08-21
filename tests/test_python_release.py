"""Tests for the bounded official Python stable-version query."""

import unittest
from unittest.mock import MagicMock, patch

import httpx

from tools.permissions import PermissionLevel, ToolAuthorization
from tools.python_release import (
    MAX_RESPONSE_BYTES,
    _extract_latest_stable_version,
    _read_latest_stable_version,
    register_python_latest_version_tool,
)
from tools.registry import ToolRegistry, ToolResultStatus
from tools.research_source import PYTHON_SOURCE_LABEL, PYTHON_SOURCE_URL


NETWORK_AUTHORITY = ToolAuthorization(allow_network=True, confirmed=True)


class FixedPythonLatestVersionToolTests(unittest.TestCase):
    def setUp(self):
        self.reader_calls = 0

        def reader():
            self.reader_calls += 1
            return "3.14.7"

        self.registry = ToolRegistry()
        register_python_latest_version_tool(self.registry, reader)

    def test_definition_is_argument_free_and_requires_network(self):
        definition = self.registry.definitions()[0]

        self.assertEqual("research.python_latest_version", definition.name)
        self.assertEqual(PermissionLevel.NETWORK, definition.permission)
        self.assertEqual((), definition.parameters)

    def test_reader_is_blocked_without_network_confirmation(self):
        result = self.registry.execute(
            "research.python_latest_version",
            {},
            ToolAuthorization(allow_network=True),
        )

        self.assertEqual(ToolResultStatus.BLOCKED, result.status)
        self.assertEqual(0, self.reader_calls)

    def test_confirmed_query_returns_only_bounded_metadata(self):
        result = self.registry.execute(
            "research.python_latest_version",
            {},
            NETWORK_AUTHORITY,
        )

        self.assertTrue(result.succeeded)
        self.assertEqual(
            {"source", "status", "version", "spoken_text"},
            set(result.output),
        )
        self.assertEqual(PYTHON_SOURCE_LABEL, result.output["source"])
        self.assertEqual("3.14.7", result.output["version"])
        self.assertNotIn("<", result.output["spoken_text"])

    def test_invalid_reader_value_is_sanitized(self):
        registry = ToolRegistry()
        register_python_latest_version_tool(registry, lambda: "3.15.0rc1")

        result = registry.execute(
            "research.python_latest_version",
            {},
            NETWORK_AUTHORITY,
        )

        self.assertEqual(ToolResultStatus.FAILED, result.status)
        self.assertEqual({}, dict(result.output))

    def test_unavailable_source_returns_no_guessed_version(self):
        registry = ToolRegistry()
        register_python_latest_version_tool(registry, lambda: None)

        result = registry.execute(
            "research.python_latest_version",
            {},
            NETWORK_AUTHORITY,
        )

        self.assertTrue(result.succeeded)
        self.assertEqual("unavailable", result.output["status"])
        self.assertEqual("", result.output["version"])

    def test_parser_selects_newest_stable_and_ignores_prerelease(self):
        page = "Python 3.15.0rc1 Python 3.14.6 Python 3.14.7 Python 3.13.15"

        self.assertEqual("3.14.7", _extract_latest_stable_version(page))

    def test_parser_rejects_page_without_stable_release(self):
        self.assertIsNone(_extract_latest_stable_version("Python 3.15.0rc1"))

    @patch("tools.python_release.httpx.Client")
    def test_default_reader_uses_only_fixed_bounded_html_request(self, client_type):
        response, client = _mock_stream(client_type, (
            b"Python 3.14.7 ",
            b"Python 3.15.0rc1",
        ))

        self.assertEqual("3.14.7", _read_latest_stable_version())

        _arguments, options = client_type.call_args
        self.assertFalse(options["follow_redirects"])
        self.assertGreater(options["timeout"], 0)
        self.assertEqual({"User-Agent"}, set(options["headers"]))
        client.stream.assert_called_once_with("GET", PYTHON_SOURCE_URL)
        response.iter_bytes.assert_called_once_with()

    @patch("tools.python_release.httpx.Client")
    def test_non_html_or_oversized_responses_are_rejected(self, client_type):
        _response, _client = _mock_stream(
            client_type,
            (b'"Python 3.14.7"',),
            content_type="application/json",
        )
        self.assertIsNone(_read_latest_stable_version())

        _response, _client = _mock_stream(
            client_type,
            (b"x" * MAX_RESPONSE_BYTES, b"x"),
        )
        self.assertIsNone(_read_latest_stable_version())

    @patch("tools.python_release.httpx.Client")
    def test_transport_error_exposes_no_details(self, client_type):
        client_type.side_effect = httpx.ConnectError("private network detail")

        self.assertIsNone(_read_latest_stable_version())


def _mock_stream(client_type, chunks, content_type="text/html"):
    client = client_type.return_value.__enter__.return_value
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": content_type}
    response.iter_bytes.return_value = chunks
    client.stream.return_value.__enter__.return_value = response
    return response, client


if __name__ == "__main__":
    unittest.main()
