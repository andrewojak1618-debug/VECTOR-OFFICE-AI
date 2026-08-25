"""Classify the local WirePod-to-Vector SDK connection without content logs."""

from collections.abc import Mapping
from enum import Enum

import httpx


WIREPOD_SDK_BATTERY_PATH = "/api-sdk/get_battery"
MIN_PREFLIGHT_TIMEOUT_SECONDS = 1.0
MAX_PREFLIGHT_TIMEOUT_SECONDS = 30.0


class WirePodSdkState(Enum):
    """Describe one content-free result of the passive WirePod SDK probe."""

    READY = "ready"
    AUTHENTICATION_FAILED = "authentication-failed"
    INVALID_RESPONSE = "invalid-response"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


class WirePodSdkProbe:
    """Check one read-only WirePod SDK endpoint without exposing robot data."""

    def __init__(
        self,
        host: str,
        serial: str,
        timeout: float = 5.0,
        client: httpx.Client | None = None,
    ):
        """Initialisiert Host, Serienzuordnung und begrenzten HTTP-Client."""
        if not MIN_PREFLIGHT_TIMEOUT_SECONDS <= timeout <= MAX_PREFLIGHT_TIMEOUT_SECONDS:
            raise ValueError("WirePod SDK preflight timeout is outside the safe range.")
        self.host = host.rstrip("/")
        self.serial = serial.strip()
        self.client = client or httpx.Client(timeout=timeout)

    def check(self) -> WirePodSdkState:
        """Prüft den SDK-Lesezugriff und verwirft sämtliche Antwortinhalte."""
        if not self.serial:
            return WirePodSdkState.DISABLED
        try:
            response = self.client.post(
                f"{self.host}{WIREPOD_SDK_BATTERY_PATH}",
                params={"serial": self.serial},
            )
        except httpx.TimeoutException:
            return WirePodSdkState.UNAVAILABLE
        except httpx.HTTPError:
            return WirePodSdkState.UNAVAILABLE
        return self._classify(response)

    def is_available(self) -> bool:
        """Meldet ausschließlich einen vollständig gültigen SDK-Lesezugriff."""
        return self.check() is WirePodSdkState.READY

    def _classify(self, response: httpx.Response) -> WirePodSdkState:
        """Ordnet HTTP-Status und Struktur festen inhaltsfreien Zuständen zu."""
        body = response.text.casefold()
        if response.status_code in {401, 403} or self._contains_auth_error(body):
            return WirePodSdkState.AUTHENTICATION_FAILED
        if response.status_code >= 400:
            return WirePodSdkState.UNAVAILABLE
        try:
            payload = response.json()
        except ValueError:
            return WirePodSdkState.INVALID_RESPONSE
        if not isinstance(payload, Mapping) or not isinstance(
            payload.get("status"),
            Mapping,
        ):
            return WirePodSdkState.INVALID_RESPONSE
        return WirePodSdkState.READY

    @staticmethod
    def _contains_auth_error(body: str) -> bool:
        """Erkennt ausschließlich bekannte lokale Authentifizierungsmarker."""
        return "unauthenticated" in body or "unauthorized" in body
