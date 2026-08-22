"""Tests for WirePod startup and quiet availability checks."""

import unittest
from unittest.mock import MagicMock, patch

import httpx

from vector.client import VectorClient


class VectorClientTests(unittest.TestCase):
    @patch("vector.client.httpx.get")
    def test_quiet_status_accepts_non_server_response(self, request):
        request.return_value = MagicMock(status_code=200)

        self.assertTrue(
            VectorClient("http://127.0.0.1:8080", timeout=7.0).is_available()
        )
        self.assertEqual(7.0, request.call_args.kwargs["timeout"])

    @patch("vector.client.httpx.get")
    def test_quiet_status_suppresses_transport_details(self, request):
        error_request = httpx.Request("GET", "http://127.0.0.1:8080")
        request.side_effect = httpx.ConnectError(
            "private transport detail",
            request=error_request,
        )

        with patch("builtins.print") as output:
            available = VectorClient("http://127.0.0.1:8080").is_available()

        self.assertFalse(available)
        output.assert_not_called()

    @patch("vector.client.httpx.get")
    def test_startup_check_preserves_visible_connection_error(self, request):
        error_request = httpx.Request("GET", "http://127.0.0.1:8080")
        request.side_effect = httpx.ConnectError("offline", request=error_request)

        with patch("builtins.print") as output:
            available = VectorClient("http://127.0.0.1:8080").check_wirepod()

        self.assertFalse(available)
        output.assert_called_once()

    @patch("vector.client.httpx.get")
    def test_startup_check_identifies_timeout_without_details(self, request):
        error_request = httpx.Request("GET", "http://127.0.0.1:8080")
        request.side_effect = httpx.ReadTimeout("private", request=error_request)

        with patch("builtins.print") as output:
            available = VectorClient("http://127.0.0.1:8080").check_wirepod()

        self.assertFalse(available)
        output.assert_called_once_with("WirePod connection timed out.")

    def test_invalid_wirepod_timeout_is_rejected(self):
        for timeout in (0.9, 30.1):
            with self.subTest(timeout=timeout), self.assertRaisesRegex(
                ValueError,
                "timeout",
            ):
                VectorClient("http://127.0.0.1:8080", timeout=timeout)


if __name__ == "__main__":
    unittest.main()
