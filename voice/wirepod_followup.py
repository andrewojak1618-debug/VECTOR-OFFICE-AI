"""Trigger one bounded WirePod listening turn without another wakeword."""

import math

import httpx


FOLLOW_UP_ENDPOINT = "/api-sdk/trigger_wake_word"
MIN_REQUEST_TIMEOUT_SECONDS = 1.0
MAX_REQUEST_TIMEOUT_SECONDS = 30.0


class WirePodFollowUpCapture:
    """Activate WirePod's fixed remote wakeword endpoint for one response."""

    def __init__(
        self,
        wirepod_host: str,
        vector_serial: str,
        request_timeout: float = 5.0,
        client: httpx.Client | None = None,
    ):
        """Initialisiert den lokalen Folgeaufruf mit festen sicheren Parametern."""
        serial = vector_serial.strip()
        if not serial:
            raise ValueError("WirePod follow-up requires a Vector serial.")
        if not _valid_timeout(request_timeout):
            raise ValueError("WirePod timeout must be between 1 and 30 seconds.")
        self.vector_serial = serial
        self.request_timeout = request_timeout
        self.client = client or httpx.Client(
            base_url=wirepod_host.rstrip("/"),
            timeout=request_timeout,
        )

    def activate(self) -> bool:
        """Startet genau eine lokale Aufnahme und meldet nur deren Erfolg."""
        try:
            response = self.client.post(
                FOLLOW_UP_ENDPOINT,
                params={"serial": self.vector_serial},
                timeout=self.request_timeout,
            )
        except httpx.HTTPError:
            return False
        if not 200 <= response.status_code < 300:
            return False
        normalized = response.text.casefold().strip()
        return "success" in normalized or normalized == "ok"


def _valid_timeout(value: float) -> bool:
    """Prüft die endliche HTTP-Frist gegen die gemeinsame WirePod-Grenze."""
    return (
        isinstance(value, (int, float))
        and math.isfinite(value)
        and MIN_REQUEST_TIMEOUT_SECONDS
        <= value
        <= MAX_REQUEST_TIMEOUT_SECONDS
    )
