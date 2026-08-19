"""Compare fixed German prompts across explicitly selected Ollama models."""

import argparse
from collections.abc import Sequence
from time import perf_counter

from brain.agent import Agent
from brain.providers import OllamaProvider
from config.settings import settings


QUESTIONS = (
    "Wie geht es dir?",
    "Warum erscheint der Himmel blau?",
    "Was macht einen guten Zuhörer aus?",
    "Welche Bedeutung hat Freiheit für persönliche Verantwortung?",
)


class _RecordingModel:
    """Retain fixed diagnostic responses without changing provider behavior."""

    def __init__(self, provider: OllamaProvider):
        self.provider = provider
        self.responses: list[str] = []

    def generate(self, messages) -> str:
        """Delegate one request and retain its safe fixed-prompt response."""
        response = self.provider.generate(messages)
        self.responses.append(response)
        return response


def compare_model(model: str) -> None:
    """Print fixed answers and per-turn latency for one explicit model."""
    provider = OllamaProvider(
        settings.OLLAMA_HOST,
        model,
        temperature=0.0,
    )
    total_started = perf_counter()
    for number, question in enumerate(QUESTIONS, start=1):
        _run_question(provider, model, number, question)
    elapsed = perf_counter() - total_started
    print(f"{model} total: {elapsed:.2f} seconds")


def _run_question(provider, model: str, number: int, question: str) -> None:
    started = perf_counter()
    recorder = _RecordingModel(provider)
    try:
        answer = Agent(recorder).respond(question)
    except RuntimeError as exc:
        _print_rejection(model, number, question, recorder.responses, exc)
        return
    elapsed = perf_counter() - started
    print(f"{model} #{number}: {elapsed:.2f} seconds")
    print(f"Question: {question}")
    print(f"Answer: {answer}")


def _print_rejection(model, number, question, responses, error) -> None:
    print(f"{model} #{number}: rejected after {len(responses)} responses")
    print(f"Question: {question}")
    for attempt, response in enumerate(responses, start=1):
        print(f"Rejected answer {attempt}: {response}")
    print(f"Policy result: {error}")


def _parse_models(arguments: Sequence[str] | None = None) -> tuple[str, ...]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", nargs="+", help="Explicit Ollama model names")
    namespace = parser.parse_args(arguments)
    return tuple(namespace.models)


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the fixed comparison for every requested local model."""
    for model in _parse_models(arguments):
        compare_model(model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
