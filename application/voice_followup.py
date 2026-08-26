"""Manage one bounded wakeword-free response window."""

import math
from collections.abc import Callable
from typing import Protocol

from application.voice_recovery import VoiceRecovery


MIN_FOLLOW_UP_TIMEOUT_SECONDS = 1.0
MAX_FOLLOW_UP_TIMEOUT_SECONDS = 10.0


class FollowUpCapture(Protocol):
    """Expose bounded local preparation and capture operations."""

    def prepare(self) -> bool:
        """Prüft den lokalen Aufnahmeweg ohne das Mikrofon zu öffnen."""

    def capture(self, timeout: float) -> str | None:
        """Erfasst genau eine lokale Antwort innerhalb der Frist."""

    def close(self) -> None:
        """Gibt den lokalen Aufnahmeweg beim Sitzungsende frei."""


class FollowUpCaptureUnavailable(RuntimeError):
    """Mark an unavailable local capture path without exposing details."""


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

    def update(self, awaiting_confirmation: bool) -> bool:
        """Bereitet bei offener Entscheidung höchstens eine Folgeaufnahme vor."""
        self.active = False
        if not awaiting_confirmation or self.capture is None:
            return False
        self.active = self.capture.prepare()
        return self.active

    def listen(
        self,
        default_listener: Callable[[float], str | None],
        default_timeout: float,
    ) -> str | None:
        """Nutzt lokal das kurze Fenster oder sicher den normalen Listener."""
        if not self.active or self.capture is None:
            return default_listener(default_timeout)
        try:
            user_text = self.capture.capture(self.timeout)
        except FollowUpCaptureUnavailable:
            self.active = False
            print("Local follow-up unavailable; say 'Hey Vector' to answer.")
            return default_listener(default_timeout)
        if user_text:
            print(f"Du: {user_text}")
        return user_text

    def consume_timeout(self) -> bool:
        """Beendet ein abgelaufenes Fenster und meldet den vorherigen Zustand."""
        was_active = self.active
        self.active = False
        return was_active

    def consume_transcript(self) -> None:
        """Beendet das Fenster unmittelbar nach einer erkannten Antwort."""
        self.active = False

    def close(self) -> None:
        """Schließt einen optional zustandsbehafteten lokalen Aufnahmeweg."""
        self.active = False
        if self.capture is None:
            return
        close = getattr(self.capture, "close", None)
        if callable(close):
            close()


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
        user_text = follow_up.listen(listen, default_timeout)
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
