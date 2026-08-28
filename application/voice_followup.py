"""Manage one bounded wakeword-free response window."""

import math
from collections.abc import Callable
from enum import Enum
from typing import Protocol

from application.voice_recovery import VoiceRecovery


MIN_FOLLOW_UP_TIMEOUT_SECONDS = 1.0
MAX_FOLLOW_UP_TIMEOUT_SECONDS = 10.0
FOLLOW_UP_END_PHRASES = frozenset({
    "danke",
    "danke dir",
    "danke das reicht",
    "dankeschön",
    "das reicht",
    "stopp",
    "vielen dank",
})


class FollowUpMode(Enum):
    """Unterscheidet sichere Bestätigungen von freien Inhaltsfragen."""

    CONFIRMATION = "confirmation"
    CONVERSATION = "conversation"


class FollowUpCapture(Protocol):
    """Expose bounded local preparation and capture operations."""

    def prepare(self) -> bool:
        """Prüft den lokalen Aufnahmeweg ohne das Mikrofon zu öffnen."""

    def capture(self, timeout: float, free_text: bool = False) -> str | None:
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
        self.mode: FollowUpMode | None = None

    @property
    def is_confirmation(self) -> bool:
        """Meldet ein aktives Fenster für eine kontrollierte Entscheidung."""
        return self.active and self.mode is FollowUpMode.CONFIRMATION

    @property
    def is_conversational(self) -> bool:
        """Meldet ein aktives Fenster für eine kurze inhaltliche Folgefrage."""
        return self.active and self.mode is FollowUpMode.CONVERSATION

    def update(
        self,
        awaiting_confirmation: bool,
        allow_conversation: bool = False,
    ) -> bool:
        """Bereitet genau ein priorisiertes und begrenztes Antwortfenster vor."""
        self.active = False
        self.mode = _follow_up_mode(awaiting_confirmation, allow_conversation)
        if self.mode is None or self.capture is None:
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
            user_text = self.capture.capture(
                self.timeout,
                self.is_conversational,
            )
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
        self.mode = None
        return was_active

    def consume_transcript(self) -> None:
        """Beendet das Fenster unmittelbar nach einer erkannten Antwort."""
        self.active = False
        self.mode = None

    def is_end_signal(self, user_text: str) -> bool:
        """Erkennt nur im Inhaltsfenster ein lokales Gesprächsende."""
        if not self.is_conversational:
            return False
        normalized = " ".join(user_text.casefold().strip().split())
        return normalized.rstrip(".!?,;:").strip() in FOLLOW_UP_END_PHRASES

    def close(self) -> None:
        """Schließt einen optional zustandsbehafteten lokalen Aufnahmeweg."""
        self.active = False
        self.mode = None
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
    was_confirmation = follow_up.is_confirmation
    if not follow_up.consume_timeout():
        return
    if was_confirmation:
        cancel_pending()
        print("Confirmation window expired; no action was executed.")
        return
    print("Follow-up window expired; returning to wakeword mode.")


def _valid_timeout(value: float) -> bool:
    """Prüft eine endliche Frist gegen die erlaubte Dialoggrenze."""
    return (
        isinstance(value, (int, float))
        and math.isfinite(value)
        and MIN_FOLLOW_UP_TIMEOUT_SECONDS
        <= value
        <= MAX_FOLLOW_UP_TIMEOUT_SECONDS
    )


def _follow_up_mode(
    awaiting_confirmation: bool,
    allow_conversation: bool,
) -> FollowUpMode | None:
    """Wählt Bestätigungen stets vor einem freien Inhaltsfenster."""
    if awaiting_confirmation:
        return FollowUpMode.CONFIRMATION
    if allow_conversation:
        return FollowUpMode.CONVERSATION
    return None
