"""HTTP health check for the local WirePod service."""

import httpx


WIREPOD_TIMEOUT_SECONDS = 5.0


class VectorClient:
    """Check whether the configured local WirePod host is reachable."""

    def __init__(self, wirepod_host: str):
        self.wirepod_host = wirepod_host.rstrip("/")

    def check_wirepod(self) -> bool:
        """Return whether WirePod responds without a server error."""
        try:
            response = httpx.get(
                self.wirepod_host,
                timeout=WIREPOD_TIMEOUT_SECONDS,
                follow_redirects=True,
            )

            return response.status_code < 500

        except httpx.HTTPError as exc:
            print(f"WirePod connection error: {exc}")
            return False
