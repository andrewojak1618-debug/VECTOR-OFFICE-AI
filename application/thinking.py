"""Overlap local response generation with one bounded thinking prelude."""

from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
from typing import Protocol, TypeVar


ResultValue = TypeVar("ResultValue")


class ResponseAgent(Protocol):
    """Provide the response boundary needed by the thinking coordinator."""

    def respond(self, user_text: str) -> str:
        """Erzeugt eine Antwort für normalisierten Nutzertext."""
        ...


class ThinkingSpeech(Protocol):
    """Provide an optional audible thinking prelude."""

    def say_thinking_prelude(self) -> bool:
        """Spielt eine lokal gewählte Denkphase und meldet ihren Abschluss."""
        ...


def generate_with_thinking(
    agent: ResponseAgent,
    speech: object,
    user_text: str,
) -> str:
    """Erzeugt parallel eine Antwort, während die lokale Denkphase erklingt."""
    return run_with_thinking(lambda: agent.respond(user_text), speech)


def run_with_thinking(
    task: Callable[[], ResultValue],
    speech: object,
) -> ResultValue:
    """Führt eine Antwortaufgabe während einer optionalen Denkphase aus."""
    with ThreadPoolExecutor(max_workers=1) as executor:
        response = executor.submit(task)
        _play_optional_prelude(speech)
        return response.result()


def _play_optional_prelude(speech: object) -> None:
    """Spielt die optionale Denkphase ab und hält Fehler von der Antwort fern."""
    play = getattr(speech, "say_thinking_prelude", None)
    if not callable(play):
        return
    try:
        play()
    except (OSError, RuntimeError, TypeError, ValueError):
        return
