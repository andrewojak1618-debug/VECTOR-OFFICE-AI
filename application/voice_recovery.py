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


class VoiceRecovery:
    """Apply fixed voice retry limits and consume one recovery transition."""

    def __init__(
        self,
        connections: ConnectionSupervisor | None,
        speaker: Callable[[str], bool],
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self.connections = connections
        self.speaker = speaker
        self.sleeper = sleeper

    @property
    def max_failures(self) -> int:
        """Return the fixed maximum number of consecutive voice failures."""
        return MAX_CONSECUTIVE_VOICE_FAILURES

    def retry_failure(self, failure_count: int) -> bool:
        """Wait after one failure or report that the fixed limit is exhausted."""
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
        """Record availability and speak one pending recovery exactly once."""
        if self.connections is None:
            return
        self.connections.observe("wirepod", True)
        if not self.connections.consume_recovery("wirepod"):
            return
        print(f"Vector: {CONNECTION_RECOVERY_NOTICE}")
        self.speaker(CONNECTION_RECOVERY_NOTICE)

    def _failure_delay(self) -> float:
        if self.connections is None:
            return VOICE_RETRY_DELAY_SECONDS
        return self.connections.observe(
            "wirepod",
            False,
        ).retry_after_seconds
