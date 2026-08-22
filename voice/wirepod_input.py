"""Private voice transcript input from the local WirePod log endpoint."""

import argparse
import hashlib
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime

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
DUPLICATE_TRANSCRIPT_WINDOW_SECONDS = 3.0
MAX_RECENT_TRANSCRIPTS = 50
WIREPOD_TIMESTAMP_FORMAT = "%Y.%m.%d %H:%M:%S"


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
        duplicate_window: float = DUPLICATE_TRANSCRIPT_WINDOW_SECONDS,
        client: httpx.Client | None = None,
    ):
        """Initialisiert die lokale Abfrage mit begrenzter Duplikaterkennung."""
        if not math.isfinite(duplicate_window) or not 0 <= duplicate_window <= 30:
            raise ValueError("Duplicate transcript window must be between 0 and 30.")
        self.poll_interval = poll_interval
        self.duplicate_window = duplicate_window
        self.client = client or httpx.Client(
            base_url=wirepod_host.rstrip("/"),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        self._seen_line_fingerprints: set[str] = set()
        self._recent_transcripts: dict[str, datetime] = {}
        self._primed = False

    @staticmethod
    def parse_logs(log_text: str) -> tuple[TranscriptEvent, ...]:
        """Liest unterstützte Transkriptionsereignisse aus einer WirePod-Logantwort."""
        events = (
            WirePodTranscriptListener._parse_line(line)
            for line in log_text.splitlines()
        )
        return tuple(event for event in events if event is not None)

    @staticmethod
    def _parse_line(line: str) -> TranscriptEvent | None:
        """Validiert eine Logzeile und überführt sie in ein Transkriptionsereignis."""
        normalized_line = line.strip()
        match = TRANSCRIPT_PATTERN.match(normalized_line)
        if match is None:
            return None
        timestamp = match.group("timestamp")
        try:
            datetime.strptime(timestamp, WIREPOD_TIMESTAMP_FORMAT)
        except ValueError:
            return None
        return TranscriptEvent(
            timestamp=timestamp,
            intent=match.group("intent"),
            text=match.group("text").strip(),
            device=match.group("device"),
            raw_line=normalized_line,
        )

    def prime(self) -> None:
        """Markiert vorhandene Logeinträge vor Annahme neuer Sprache als gesehen."""
        events = self._fetch_events()
        self._seen_line_fingerprints = {
            self._line_fingerprint(event) for event in events
        }
        self._primed = True

    def poll(self) -> tuple[TranscriptEvent, ...]:
        """Liefert nur Ereignisse, die keine frühere Abfrage ausgegeben hat."""
        events = self._fetch_events()
        new_events = tuple(
            event
            for event in events
            if self._line_fingerprint(event) not in self._seen_line_fingerprints
        )
        self._seen_line_fingerprints.update(
            self._line_fingerprint(event) for event in events
        )

        if len(self._seen_line_fingerprints) > MAX_SEEN_LINES:
            self._seen_line_fingerprints = {
                self._line_fingerprint(event)
                for event in events[-RETAINED_SEEN_LINES:]
            }

        self._primed = True
        return new_events

    def wait_for_transcript(
        self,
        timeout: float = 60.0,
    ) -> TranscriptEvent | None:
        """Wartet bis zum Fristende auf genau ein aussagekräftiges Transkript."""
        if not self._primed:
            self.prime()

        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            events = self.poll()
            event = self._latest_unique_spoken_event(events)
            if event is not None:
                return event

            time.sleep(self.poll_interval)

        return None

    @staticmethod
    def _spoken_events(events) -> tuple[TranscriptEvent, ...]:
        """Entfernt leere Ereignisse und reine Kein-Audio-Systemmeldungen."""
        return tuple(
            event
            for event in events
            if event.text and event.intent != "intent_system_noaudio"
        )

    def _latest_unique_spoken_event(
        self,
        events: tuple[TranscriptEvent, ...],
    ) -> TranscriptEvent | None:
        """Wählt rückwärts das jüngste noch nicht duplizierte Sprachereignis."""
        for event in reversed(self._spoken_events(events)):
            if self._accept_transcript(event):
                return event
        return None

    def _accept_transcript(self, event: TranscriptEvent) -> bool:
        """Unterdrückt gleiche Transkripte innerhalb des festgelegten Zeitfensters."""
        fingerprint = self._transcript_fingerprint(event)
        event_time = datetime.strptime(
            event.timestamp,
            WIREPOD_TIMESTAMP_FORMAT,
        )
        previous_time = self._recent_transcripts.get(fingerprint)
        if previous_time is not None:
            elapsed = abs((event_time - previous_time).total_seconds())
            if elapsed <= self.duplicate_window:
                return False
        self._recent_transcripts[fingerprint] = event_time
        self._limit_recent_transcripts()
        return True

    def _limit_recent_transcripts(self) -> None:
        """Begrenzt die sitzungslokale Duplikathistorie auf die jüngsten Einträge."""
        if len(self._recent_transcripts) <= MAX_RECENT_TRANSCRIPTS:
            return
        newest = sorted(
            self._recent_transcripts.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:MAX_RECENT_TRANSCRIPTS]
        self._recent_transcripts = dict(newest)

    @staticmethod
    def _transcript_fingerprint(event: TranscriptEvent) -> str:
        """Hasht Gerät und normalisierten Text ohne Speicherung des Klartexts."""
        normalized_text = " ".join(
            event.text.casefold().strip().rstrip(".!?").split()
        )
        value = f"{event.device.casefold()}\0{normalized_text}"
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _line_fingerprint(event: TranscriptEvent) -> str:
        """Hasht eine vollständige Logzeile für die einmalige Ausgabe."""
        return hashlib.sha256(event.raw_line.encode("utf-8")).hexdigest()

    def _fetch_events(self) -> tuple[TranscriptEvent, ...]:
        """Ruft lokale WirePod-Logs ab und bereinigt Transportfehler."""
        try:
            response = self.client.get("/api/get_logs")
            response.raise_for_status()
        except httpx.HTTPError:
            raise RuntimeError(
                "WirePod transcript endpoint is unavailable."
            ) from None

        return self.parse_logs(response.text)


def main() -> None:
    """Wartet auf ein neues lokales WirePod-Transkript und gibt es aus."""
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
