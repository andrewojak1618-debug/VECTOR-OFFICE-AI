"""HTTP health check for the local WirePod service."""

import httpx


MIN_WIREPOD_TIMEOUT_SECONDS = 1.0
MAX_WIREPOD_TIMEOUT_SECONDS = 30.0


class VectorClient:
    """Check whether the configured local WirePod host is reachable."""

    def __init__(self, wirepod_host: str, timeout: float = 5.0):
        """Initialisiert die lokale WirePod-Adresse ohne abschließenden Schrägstrich."""
        if not (
            MIN_WIREPOD_TIMEOUT_SECONDS
            <= timeout
            <= MAX_WIREPOD_TIMEOUT_SECONDS
        ):
            raise ValueError("WirePod timeout must be between 1 and 30 seconds.")
        self.wirepod_host = wirepod_host.rstrip("/")
        self.timeout = timeout

    def check_wirepod(self) -> bool:
        """Meldet, ob WirePod ohne Serverfehler antwortet."""
        return self._check_wirepod(report_error=True)

    def is_available(self) -> bool:
        """Prüft WirePod still für eine begrenzte Statusausgabe."""
        return self._check_wirepod(report_error=False)

    def _check_wirepod(self, report_error: bool) -> bool:
        """Führt die zeitlich begrenzte HTTP-Prüfung mit optionaler Fehlermeldung aus."""
        try:
            response = httpx.get(
                self.wirepod_host,
                timeout=self.timeout,
                follow_redirects=True,
            )

            return response.status_code < 500

        except httpx.TimeoutException:
            if report_error:
                print("WirePod connection timed out.")
            return False
        except httpx.HTTPError:
            if report_error:
                print("WirePod connection failed.")
            return False
