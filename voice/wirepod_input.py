"""Private voice transcript input from the local WirePod log endpoint."""

import argparse
import re
import time
from dataclasses import dataclass

import httpx


TRANSCRIPT_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}): "
    r"Intent matched: (?P<intent>.*?), transcribed text: "
    r"'(?P<text>.*)', device: (?P<device>\S+)$"
)
DEFAULT_POLL_INTERVAL = 0.5
REQUEST_TIMEOUT_SECONDS = 5.0
MAX_SEEN_LINES = 200
RETAINED_SEEN_LINES = 50


@dataclass(frozen=True)
class TranscriptEvent:
    """One parsed WirePod speech-recognition event."""

    timestamp: str
    intent: str
    text: str
    device: str
    raw_line: str


class WirePodTranscriptListener:
    """Poll WirePod and emit each newly recognized transcript once."""

    def __init__(
        self,
        wirepod_host: str,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        client: httpx.Client | None = None,
    ):
        self.poll_interval = poll_interval
        self.client = client or httpx.Client(
            base_url=wirepod_host.rstrip("/"),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        self._seen_lines: set[str] = set()
        self._primed = False

    @staticmethod
    def parse_logs(log_text: str) -> tuple[TranscriptEvent, ...]:
        """Parse supported transcript events from a WirePod log response."""
        events = (
            WirePodTranscriptListener._parse_line(line)
            for line in log_text.splitlines()
        )
        return tuple(event for event in events if event is not None)

    @staticmethod
    def _parse_line(line: str) -> TranscriptEvent | None:
        normalized_line = line.strip()
        match = TRANSCRIPT_PATTERN.match(normalized_line)
        if match is None:
            return None
        return TranscriptEvent(
            timestamp=match.group("timestamp"),
            intent=match.group("intent"),
            text=match.group("text").strip(),
            device=match.group("device"),
            raw_line=normalized_line,
        )

    def prime(self) -> None:
        """Mark current log entries as seen before accepting new speech."""
        events = self._fetch_events()
        self._seen_lines = {event.raw_line for event in events}
        self._primed = True

    def poll(self) -> tuple[TranscriptEvent, ...]:
        """Return only events not emitted by an earlier poll."""
        events = self._fetch_events()
        new_events = tuple(
            event for event in events if event.raw_line not in self._seen_lines
        )
        self._seen_lines.update(event.raw_line for event in events)

        if len(self._seen_lines) > MAX_SEEN_LINES:
            self._seen_lines = {
                event.raw_line for event in events[-RETAINED_SEEN_LINES:]
            }

        self._primed = True
        return new_events

    def wait_for_transcript(
        self,
        timeout: float = 60.0,
    ) -> TranscriptEvent | None:
        """Wait for one meaningful transcript until the timeout expires."""
        if not self._primed:
            self.prime()

        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            events = self.poll()
            spoken_events = self._spoken_events(events)

            if spoken_events:
                return spoken_events[-1]

            time.sleep(self.poll_interval)

        return None

    @staticmethod
    def _spoken_events(events) -> tuple[TranscriptEvent, ...]:
        return tuple(
            event
            for event in events
            if event.text and event.intent != "intent_system_noaudio"
        )

    def _fetch_events(self) -> tuple[TranscriptEvent, ...]:
        try:
            response = self.client.get("/api/get_logs")
            response.raise_for_status()
        except httpx.HTTPError:
            raise RuntimeError(
                "WirePod transcript endpoint is unavailable."
            ) from None

        return self.parse_logs(response.text)


def main() -> None:
    """Wait for and print one new local WirePod transcript."""
    parser = argparse.ArgumentParser(
        description="Wait for one new transcript from the local WirePod.",
    )
    parser.add_argument(
        "--host",
        default="http://127.0.0.1:8080",
        help="WirePod base URL",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Maximum wait time in seconds",
    )
    arguments = parser.parse_args()
    listener = WirePodTranscriptListener(arguments.host)

    print("Waiting for a new Vector voice transcript...")
    event = listener.wait_for_transcript(arguments.timeout)

    if event is None:
        print("No new transcript received before the timeout.")
        raise SystemExit(1)

    print(f"Device:     {event.device}")
    print(f"Intent:     {event.intent}")
    print(f"Transcript: {event.text}")


if __name__ == "__main__":
    main()
