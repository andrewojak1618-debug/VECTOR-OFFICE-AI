"""Coordinate bounded WirePod retries and one local recovery announcement."""

import time
from collections.abc import Callable

from application.connection_supervisor import (
    DEFAULT_RETRY_DELAYS,
    ConnectionSupervisor,
)


MAX_CONSECUTIVE_VOICE_FAILURES = len(DEFAULT_RETRY_DELAYS)
VOICE_RETRY_DELAY_SECONDS = 0.5
CONNECTION_RECOVERY_NOTICE = (
    "Meine Verbindung war kurz unterbrochen. "
    "Jetzt bin ich wieder erreichbar."
)
CONNECTION_OFFLINE_NOTICE = (
    "Ich kann deine Spracheingabe gerade nicht erreichen. "
    "Ich versuche die Verbindung wiederherzustellen."
)


class VoiceRecovery:
    """Apply fixed voice retry limits and consume one recovery transition."""

    def __init__(
        self,
        connections: ConnectionSupervisor | None,
        speaker: Callable[[str], bool],
        sleeper: Callable[[float], None] = time.sleep,
    ):
        """Initialisiert begrenzte Voice-Retries und die lokale Wiederherstellungsansage."""
        self.connections = connections
        self.speaker = speaker
        self.sleeper = sleeper
        self._outage_announced = False

    @property
    def max_failures(self) -> int:
        """Liefert die feste Höchstzahl aufeinanderfolgender Spracheingabefehler."""
        return MAX_CONSECUTIVE_VOICE_FAILURES

    def retry_failure(self, failure_count: int) -> bool:
        """Wartet nach einem Fehler oder meldet das Erreichen der festen Grenze."""
        self._announce_outage_once()
        if failure_count >= self.max_failures:
            print("Voice input failed repeatedly. Conversation ended.")
            return False
        print(
            "Voice input temporarily unavailable "
            f"({failure_count}/{self.max_failures}). Retrying..."
        )
        self.sleeper(self._failure_delay())
        return True

    def complete(self) -> None:
        """Speichert Verfügbarkeit und spricht eine Wiederherstellung genau einmal."""
        if self.connections is None:
            self._outage_announced = False
            return
        self.connections.observe("wirepod", True)
        recovered = self.connections.consume_recovery("wirepod")
        self._outage_announced = False
        if not recovered:
            return
        print(f"Vector: {CONNECTION_RECOVERY_NOTICE}")
        self.speaker(CONNECTION_RECOVERY_NOTICE)

    def _announce_outage_once(self) -> None:
        """Spricht den ersten WirePod-Ausfall eines Übergangs genau einmal."""
        if self._outage_announced:
            return
        self._outage_announced = True
        print(f"Vector: {CONNECTION_OFFLINE_NOTICE}")
        self.speaker(CONNECTION_OFFLINE_NOTICE)

    def _failure_delay(self) -> float:
        """Liefert die überwachte oder lokale feste Wartezeit nach Voice-Ausfall."""
        if self.connections is None:
            return VOICE_RETRY_DELAY_SECONDS
        return self.connections.observe(
            "wirepod",
            False,
        ).retry_after_seconds
