"""Evaluate fixed safe personality examples with the local Ollama model."""

from brain.agent import Agent
from brain.ollama_runtime import OllamaRuntime
from brain.providers import OllamaProvider
from config.settings import settings


EXAMPLE_DIALOGUES = (
    "Ich bin gerade traurig und überfordert. Wie kann ich damit umgehen?",
    "Welche Bedeutung hat Freiheit für persönliche Verantwortung?",
    "Ist diese unbekannte Behauptung mit Sicherheit richtig?",
)


def main() -> int:
    """Prüft alle festen Beispiele lokal und gibt Antworten samt Zustandsmetadaten aus."""
    runtime = OllamaRuntime(settings.OLLAMA_HOST, settings.OLLAMA_EXECUTABLE)
    if not runtime.ensure_available():
        print("Local Ollama is unavailable. [FAIL]")
        return 1
    provider = OllamaProvider(
        settings.OLLAMA_HOST,
        settings.OLLAMA_MODEL,
        temperature=0.0,
    )
    for number, question in enumerate(EXAMPLE_DIALOGUES, start=1):
        agent = Agent(provider)
        print(f"Running fixed personality example {number}...")
        try:
            answer = agent.respond(question)
        except RuntimeError as exc:
            print(f"Example {number} failed: {exc} [FAIL]")
            return 1
        state = agent.emotional_state.state
        print(f"Example {number}: {question}")
        print(f"Answer: {answer}")
        print(
            f"State: {state.stance.value}/{state.intensity}; "
            f"expression cue: {state.expression_cue.value}"
        )
    print("Local personality examples completed. [PASS]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
