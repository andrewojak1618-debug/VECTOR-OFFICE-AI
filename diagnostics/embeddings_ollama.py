"""Run a privacy-safe real embedding check against local Ollama."""

from brain.ollama_runtime import OllamaRuntime
from config.settings import settings
from memory.embeddings import (
    EmbeddingError,
    EmbeddingModelUnavailableError,
    EmbeddingResult,
    EmbeddingText,
    create_embedding_provider,
)


DIAGNOSTIC_TEXTS = (
    EmbeddingText("Vector verwaltet bestätigte Erinnerungen lokal."),
    EmbeddingText("Dokumentabschnitte werden für die lokale Suche vorbereitet."),
    EmbeddingText("Die semantischen Vektoren verlassen diesen Computer nicht."),
)


def run_diagnostic() -> bool:
    """Verify model availability and one real local batch embedding request."""
    if not _ensure_ollama():
        return False
    provider = create_embedding_provider(settings)
    try:
        model_info = provider.ensure_model_available()
        results = provider.embed_many(DIAGNOSTIC_TEXTS)
    except EmbeddingModelUnavailableError as exc:
        print(f"Embedding model unavailable: {exc} [ERROR]")
        return False
    except EmbeddingError as exc:
        print(f"Local embedding diagnostic failed: {exc} [ERROR]")
        return False
    return _report_success(model_info.model_name, results)


def _ensure_ollama() -> bool:
    runtime = OllamaRuntime(settings.OLLAMA_HOST, settings.OLLAMA_EXECUTABLE)
    if runtime.ensure_available():
        return True
    print("Local Ollama service is unavailable. [ERROR]")
    return False


def _report_success(
    model_name: str,
    results: tuple[EmbeddingResult, ...],
) -> bool:
    dimensions = {result.dimension for result in results}
    if len(results) != len(DIAGNOSTIC_TEXTS) or len(dimensions) != 1:
        print("Local Ollama returned inconsistent embeddings. [ERROR]")
        return False
    print(f"Embedding model: {model_name}")
    print(f"Embedding dimension: {dimensions.pop()}")
    print(f"Generated vectors: {len(results)}")
    print("No input texts or vector values were logged. [OK]")
    print("Local Ollama embedding diagnostic passed. [OK]")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if run_diagnostic() else 1)
