"""Verify real local document embeddings persisted in temporary SQLite."""

import tempfile
from pathlib import Path

from brain.ollama_runtime import OllamaRuntime
from config.settings import settings
from memory.embedding_store import SQLiteEmbeddingStore, StoredEmbedding
from memory.embeddings import EmbeddingError, create_embedding_provider
from memory.indexing import DocumentEmbeddingIndexer, IndexedKnowledgeLibrary
from memory.library import SQLiteKnowledgeLibrary


DIAGNOSTIC_DOCUMENT = (
    "Vector Office AI verwaltet bestätigte Erinnerungen ausschließlich lokal.\n\n"
    "Dokumentabschnitte erhalten nachvollziehbare semantische Vektoren.\n\n"
    "Modellversion und Dimension machen gespeicherte Vektoren überprüfbar."
)


def run_diagnostic() -> bool:
    """Import, embed, store, and reload one safe temporary document."""
    if not _ensure_ollama():
        return False
    try:
        with tempfile.TemporaryDirectory(prefix="vector-embedding-store-") as root:
            return _run_in_directory(Path(root))
    except (EmbeddingError, OSError, ValueError) as exc:
        print(f"Embedding storage diagnostic failed: {exc} [ERROR]")
        return False


def _run_in_directory(root: Path) -> bool:
    document_path = root / "diagnostic.md"
    document_path.write_text(DIAGNOSTIC_DOCUMENT, encoding="utf-8")
    database_path = root / "diagnostic.db"
    raw_library = SQLiteKnowledgeLibrary(database_path, chunk_size=100)
    store = SQLiteEmbeddingStore(database_path)
    provider = create_embedding_provider(settings)
    indexer = DocumentEmbeddingIndexer(raw_library, store, provider)
    library = IndexedKnowledgeLibrary(raw_library, indexer)
    document = library.import_document(str(document_path)).document
    stored = store.list_for_document(document.id)
    return _report_success(
        stored,
        provider.model_version,
    )


def _ensure_ollama() -> bool:
    runtime = OllamaRuntime(settings.OLLAMA_HOST, settings.OLLAMA_EXECUTABLE)
    if runtime.ensure_available():
        return True
    print("Local Ollama service is unavailable. [ERROR]")
    return False


def _report_success(
    stored: tuple[StoredEmbedding, ...],
    model_version: str | None,
) -> bool:
    if not stored or model_version is None:
        print("No versioned embeddings were stored. [ERROR]")
        return False
    dimensions = {embedding.dimension for embedding in stored}
    if len(dimensions) != 1:
        print("Stored embedding dimensions are inconsistent. [ERROR]")
        return False
    print(f"Stored embeddings: {len(stored)}")
    print(f"Stored dimension: {dimensions.pop()}")
    print(f"Model version recorded: {model_version[:12]}...")
    print("No document texts or vector values were logged. [OK]")
    print("Local document embedding storage diagnostic passed. [OK]")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if run_diagnostic() else 1)
