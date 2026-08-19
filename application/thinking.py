"""Overlap local response generation with one bounded thinking prelude."""

from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
from typing import Protocol, TypeVar


ResultValue = TypeVar("ResultValue")


class ResponseAgent(Protocol):
    """Provide the response boundary needed by the thinking coordinator."""

    def respond(self, user_text: str) -> str:
        """Generate one response for normalized user text."""
        ...


class ThinkingSpeech(Protocol):
    """Provide an optional audible thinking prelude."""

    def say_thinking_prelude(self) -> bool:
        """Play one locally selected prelude and report completion."""
        ...


def generate_with_thinking(
    agent: ResponseAgent,
    speech: object,
    user_text: str,
) -> str:
    """Generate in parallel while a sequential local prelude is spoken."""
    return run_with_thinking(lambda: agent.respond(user_text), speech)


def run_with_thinking(
    task: Callable[[], ResultValue],
    speech: object,
) -> ResultValue:
    """Run one response task while the optional local prelude is playing."""
    with ThreadPoolExecutor(max_workers=1) as executor:
        response = executor.submit(task)
        _play_optional_prelude(speech)
        return response.result()


def _play_optional_prelude(speech: object) -> None:
    play = getattr(speech, "say_thinking_prelude", None)
    if not callable(play):
        return
    try:
        play()
    except (OSError, RuntimeError, TypeError, ValueError):
        return
