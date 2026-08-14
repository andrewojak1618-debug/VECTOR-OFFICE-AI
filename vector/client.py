import httpx


class VectorClient:
    def __init__(self, wirepod_host: str):
        self.wirepod_host = wirepod_host.rstrip("/")

    def check_wirepod(self) -> bool:
        try:
            response = httpx.get(
                self.wirepod_host,
                timeout=5.0,
                follow_redirects=True,
            )

            return response.status_code < 500

        except httpx.HTTPError as exc:
            print(f"WirePod connection error: {exc}")
            return False