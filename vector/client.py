"""HTTP health check for the local WirePod service."""

import httpx


WIREPOD_TIMEOUT_SECONDS = 5.0


class VectorClient:
    """Check whether the configured local WirePod host is reachable."""

    def __init__(self, wirepod_host: str):
        """Initialisiert die lokale WirePod-Adresse ohne abschließenden Schrägstrich."""
        self.wirepod_host = wirepod_host.rstrip("/")

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
                timeout=WIREPOD_TIMEOUT_SECONDS,
                follow_redirects=True,
            )

            return response.status_code < 500

        except httpx.HTTPError as exc:
            if report_error:
                print(f"WirePod connection error: {exc}")
            return False
