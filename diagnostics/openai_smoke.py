"""Verify one minimal OpenAI response without exposing credentials or content."""

from brain.context import ChatMessage
from brain.providers import OpenAIProvider
from config.settings import settings


SMOKE_MESSAGES = (
    ChatMessage(
        role="system",
        content="Antworte knapp auf Deutsch. Gib keine vertraulichen Daten aus.",
    ),
    ChatMessage(role="user", content="Bestätige die Erreichbarkeit mit einem Wort."),
)


def run_diagnostic(provider: OpenAIProvider | None = None) -> bool:
    """Return whether the configured OpenAI model produced non-empty text."""
    if provider is None and not settings.OPENAI_API_KEY.strip():
        print("OPENAI_API_KEY is not configured. [FAIL]")
        return False
    model = provider or OpenAIProvider(
        settings.OPENAI_API_KEY,
        settings.OPENAI_MODEL,
    )
    try:
        response = model.generate(SMOKE_MESSAGES).strip()
    except RuntimeError as exc:
        print(f"OpenAI smoke test failed: {exc} [FAIL]")
        return False
    if not response:
        print("OpenAI returned an empty response. [FAIL]")
        return False
    print(f"OpenAI model {model.model} is reachable. [PASS]")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if run_diagnostic() else 1)
