"""Manage one bounded wakeword-free response window."""

import math
from collections.abc import Callable
from typing import Protocol

from application.voice_recovery import VoiceRecovery


MIN_FOLLOW_UP_TIMEOUT_SECONDS = 1.0
MAX_FOLLOW_UP_TIMEOUT_SECONDS = 10.0


class FollowUpCapture(Protocol):
    """Expose the only operation needed to start a follow-up recording."""

    def activate(self) -> bool:
        """Startet genau eine begrenzte Folgeaufnahme."""


class VoiceFollowUpWindow:
    """Track whether the next listener wait belongs to a confirmation."""

    def __init__(
        self,
        capture: FollowUpCapture | None,
        timeout: float = 5.0,
    ):
        """Initialisiert ein inaktives und zeitlich begrenztes Antwortfenster."""
        if not _valid_timeout(timeout):
            raise ValueError("Voice follow-up timeout must be between 1 and 10 seconds.")
        self.capture = capture
        self.timeout = timeout
        self.active = False

    def listening_timeout(self, default: float) -> float:
        """Wählt für eine aktive Bestätigung die kurze Aufnahmefrist."""
        return self.timeout if self.active else default

    def update(self, awaiting_confirmation: bool) -> bool:
        """Aktiviert bei offener Entscheidung höchstens eine Folgeaufnahme."""
        self.active = False
        if not awaiting_confirmation or self.capture is None:
            return False
        self.active = self.capture.activate()
        return self.active

    def consume_timeout(self) -> bool:
        """Beendet ein abgelaufenes Fenster und meldet den vorherigen Zustand."""
        was_active = self.active
        self.active = False
        return was_active

    def consume_transcript(self) -> None:
        """Beendet das Fenster unmittelbar nach einer erkannten Antwort."""
        self.active = False


def receive_voice_turn(
    listen: Callable[[float], str | None],
    follow_up: VoiceFollowUpWindow,
    recovery: VoiceRecovery,
    cancel_pending: Callable[[], None],
    default_timeout: float,
    failures: int,
) -> tuple[str | None, int, bool]:
    """Empfängt einen Sprachturn und begrenzt Fehler sowie Bestätigungsfristen."""
    try:
        user_text = listen(follow_up.listening_timeout(default_timeout))
    except RuntimeError:
        _expire_follow_up(follow_up, cancel_pending)
        failures += 1
        return None, failures, recovery.retry_failure(failures)
    recovery.complete()
    if user_text is None:
        _expire_follow_up(follow_up, cancel_pending)
    return user_text, 0, True


def _expire_follow_up(
    follow_up: VoiceFollowUpWindow,
    cancel_pending: Callable[[], None],
) -> None:
    """Verwirft nach abgelaufener Folgeaufnahme jede offene Aktion."""
    if not follow_up.consume_timeout():
        return
    cancel_pending()
    print("Confirmation window expired; no action was executed.")


def _valid_timeout(value: float) -> bool:
    """Prüft eine endliche Frist gegen die erlaubte Dialoggrenze."""
    return (
        isinstance(value, (int, float))
        and math.isfinite(value)
        and MIN_FOLLOW_UP_TIMEOUT_SECONDS
        <= value
        <= MAX_FOLLOW_UP_TIMEOUT_SECONDS
    )
