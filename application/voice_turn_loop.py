"""Steuert begrenzte normale und wakeword-freie Sprachturns."""

from collections.abc import Callable
from dataclasses import dataclass

from application.voice_followup import VoiceFollowUpWindow, receive_voice_turn
from application.voice_recovery import VoiceRecovery


VOICE_EXIT_PHRASES = frozenset({
    "beende das gespräch",
    "bitte beenden",
    "dialog beenden",
    "gespräch abbrechen",
    "gespräch beenden",
    "programm beenden",
    "vector bitte beenden",
    "vector beenden",
    "vektor bitte beenden",
    "vektor beenden",
})


@dataclass(frozen=True)
class VoiceTurnCallbacks:
    """Bündelt die kontrollierten Seitengrenzen des Sprachdialogs."""

    listen: Callable[[float], str | None]
    handle: Callable[[str], bool]
    awaiting_confirmation: Callable[[], bool]
    cancel_pending: Callable[[], None]
    acknowledge_end: Callable[[], None]


@dataclass(frozen=True)
class _VoiceTurnOutcome:
    """Beschreibt das sichere Ergebnis einer empfangenen Spracheingabe."""

    completed: bool
    allow_follow_up: bool = False
    end_session: bool = False


def run_voice_turns(
    callbacks: VoiceTurnCallbacks,
    follow_up: VoiceFollowUpWindow,
    recovery: VoiceRecovery,
    default_timeout: float,
    max_turns: int | None,
    conversation_follow_up: bool,
) -> None:
    """Verarbeitet Spracheingaben mit begrenzten Folgefenstern."""
    completed_turns = 0
    failures = 0
    while max_turns is None or completed_turns < max_turns:
        user_text, failures, keep_running = receive_voice_turn(
            callbacks.listen,
            follow_up,
            recovery,
            callbacks.cancel_pending,
            default_timeout,
            failures,
        )
        if not keep_running:
            return
        outcome = _route_voice_text(user_text, follow_up, callbacks)
        if outcome.end_session:
            return
        if not outcome.completed:
            continue
        completed_turns += 1
        _prepare_next_window(
            callbacks,
            follow_up,
            outcome.allow_follow_up and conversation_follow_up,
            max_turns is None or completed_turns < max_turns,
        )


def _route_voice_text(
    user_text: str | None,
    follow_up: VoiceFollowUpWindow,
    callbacks: VoiceTurnCallbacks,
) -> _VoiceTurnOutcome:
    """Ordnet Ende, Folgeabschluss oder regulären Turn eindeutig zu."""
    if user_text is None:
        return _VoiceTurnOutcome(False)
    end_follow_up = follow_up.is_end_signal(user_text)
    follow_up.consume_transcript()
    if end_follow_up:
        callbacks.cancel_pending()
        callbacks.acknowledge_end()
        return _VoiceTurnOutcome(False)
    if _is_voice_exit_signal(user_text):
        print("Conversation ended.")
        return _VoiceTurnOutcome(False, end_session=True)
    return _VoiceTurnOutcome(True, callbacks.handle(user_text))


def _prepare_next_window(
    callbacks: VoiceTurnCallbacks,
    follow_up: VoiceFollowUpWindow,
    allow_conversation: bool,
    has_next_turn: bool,
) -> None:
    """Aktiviert höchstens ein priorisiertes lokales Antwortfenster."""
    if not has_next_turn:
        return
    if follow_up.update(
        callbacks.awaiting_confirmation(),
        allow_conversation,
    ):
        print("Listening once without another wakeword...")


def _is_voice_exit_signal(user_text: str) -> bool:
    """Erkennt feste gesprochene Signale zum kontrollierten Sitzungsende."""
    normalized = " ".join(user_text.casefold().strip().split())
    normalized = normalized.rstrip(".!?,;:").strip()
    return normalized in VOICE_EXIT_PHRASES
