"""Tests for the content-free WirePod SDK preflight."""

import unittest
from unittest.mock import MagicMock, patch

import httpx

from application.wirepod_preflight import WirePodSdkProbe, WirePodSdkState


class WirePodSdkProbeTests(unittest.TestCase):
    def test_valid_battery_response_is_ready(self):
        response = MagicMock(status_code=200)
        response.text = '{"status":{"code":1},"battery_level":3}'
        response.json.return_value = {"status": {"code": 1}, "battery_level": 3}
        client = MagicMock()
        client.post.return_value = response

        state = WirePodSdkProbe(
            "http://127.0.0.1:8080",
            "private-serial",
            client=client,
        ).check()

        self.assertIs(WirePodSdkState.READY, state)

    def test_unauthorized_rpc_response_is_recognized_without_output(self):
        response = MagicMock(status_code=200)
        response.text = "rpc error: code = Unauthenticated desc = 401 Unauthorized"
        client = MagicMock()
        client.post.return_value = response

        with patch("builtins.print") as output:
            state = WirePodSdkProbe(
                "http://127.0.0.1:8080",
                "private-serial",
                client=client,
            ).check()

        self.assertIs(WirePodSdkState.AUTHENTICATION_FAILED, state)
        output.assert_not_called()

    def test_invalid_json_response_is_rejected(self):
        response = MagicMock(status_code=200, text="not-json")
        response.json.side_effect = ValueError("private response")
        client = MagicMock()
        client.post.return_value = response

        state = WirePodSdkProbe(
            "http://127.0.0.1:8080",
            "private-serial",
            client=client,
        ).check()

        self.assertIs(WirePodSdkState.INVALID_RESPONSE, state)

    def test_transport_timeout_is_unavailable(self):
        request = httpx.Request("POST", "http://127.0.0.1:8080")
        client = MagicMock()
        client.post.side_effect = httpx.ReadTimeout("private", request=request)

        state = WirePodSdkProbe(
            "http://127.0.0.1:8080",
            "private-serial",
            client=client,
        ).check()

        self.assertIs(WirePodSdkState.UNAVAILABLE, state)

    def test_missing_serial_is_disabled_without_request(self):
        client = MagicMock()

        state = WirePodSdkProbe(
            "http://127.0.0.1:8080",
            "",
            client=client,
        ).check()

        self.assertIs(WirePodSdkState.DISABLED, state)
        client.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
