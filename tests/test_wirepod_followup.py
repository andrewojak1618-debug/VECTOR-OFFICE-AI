"""Tests for bounded wakeword-free WirePod follow-up capture."""

import unittest

import httpx

from voice.wirepod_followup import WirePodFollowUpCapture


class FakeResponse:
    def __init__(self, status_code=200, text="success"):
        self.status_code = status_code
        self.text = text


class RecordingClient:
    def __init__(self, response=None, error=None):
        self.response = response or FakeResponse()
        self.error = error
        self.calls = []

    def post(self, path, *, params, timeout):
        self.calls.append((path, params, timeout))
        if self.error is not None:
            raise self.error
        return self.response


class WirePodFollowUpCaptureTests(unittest.TestCase):
    def test_activate_uses_only_fixed_local_endpoint_and_serial(self):
        client = RecordingClient()
        capture = WirePodFollowUpCapture(
            "http://127.0.0.1:8080",
            "0dd1fd3b",
            request_timeout=2.0,
            client=client,
        )

        self.assertTrue(capture.activate())
        self.assertEqual(
            [(
                "/api-sdk/trigger_wake_word",
                {"serial": "0dd1fd3b"},
                2.0,
            )],
            client.calls,
        )

    def test_activate_rejects_http_and_unrecognized_responses(self):
        for response in (
            FakeResponse(503, "unavailable"),
            FakeResponse(200, "unexpected response"),
        ):
            with self.subTest(response=response.text):
                capture = WirePodFollowUpCapture(
                    "http://127.0.0.1:8080",
                    "0dd1fd3b",
                    client=RecordingClient(response=response),
                )
                self.assertFalse(capture.activate())

    def test_activate_handles_timeout_without_exposing_details(self):
        request = httpx.Request("POST", "http://127.0.0.1:8080")
        client = RecordingClient(
            error=httpx.ReadTimeout("private", request=request),
        )
        capture = WirePodFollowUpCapture(
            "http://127.0.0.1:8080",
            "0dd1fd3b",
            client=client,
        )

        self.assertFalse(capture.activate())

    def test_constructor_requires_serial_and_bounded_timeout(self):
        with self.assertRaises(ValueError):
            WirePodFollowUpCapture("http://127.0.0.1:8080", "")
        for timeout in (0.9, 30.1):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                WirePodFollowUpCapture(
                    "http://127.0.0.1:8080",
                    "0dd1fd3b",
                    request_timeout=timeout,
                )


if __name__ == "__main__":
    unittest.main()
