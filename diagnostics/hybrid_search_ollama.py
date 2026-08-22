"""Verify hybrid document retrieval with real local Ollama embeddings."""

import tempfile
from pathlib import Path

from brain.ollama_runtime import OllamaRuntime
from config.settings import settings
from memory.embedding_store import SQLiteEmbeddingStore
from memory.embeddings import EmbeddingError, create_embedding_provider
from memory.indexing import DocumentEmbeddingIndexer, IndexedKnowledgeLibrary
from memory.library import SQLiteKnowledgeLibrary
from memory.search import HybridKnowledgeSearch, HybridSearchConfig


TARGET_TEXT = "Microsoft Stefan erzeugt die deutsche Stimme des Roboters."
DISTRACTOR_TEXT = "SQLite bewahrt bestätigte Erinnerungen dauerhaft lokal auf."
SEMANTIC_QUERY = "Wer übernimmt die Sprachausgabe?"


def run_diagnostic() -> bool:
    """Prüft eine isolierte semantische Suche ohne Dokumentinhalte zu protokollieren."""
    runtime = OllamaRuntime(settings.OLLAMA_HOST, settings.OLLAMA_EXECUTABLE)
    if not runtime.ensure_available():
        print("Local Ollama service is unavailable. [ERROR]")
        return False
    try:
        with tempfile.TemporaryDirectory(prefix="vector-hybrid-search-") as root:
            return _run_in_directory(Path(root))
    except (EmbeddingError, OSError, ValueError) as exc:
        print(f"Hybrid search diagnostic failed: {exc} [ERROR]")
        return False


def _run_in_directory(root: Path) -> bool:
    """Baut eine isolierte hybride Suche auf und prüft ihren ersten Treffer."""
    database_path = root / "diagnostic.db"
    raw_library = SQLiteKnowledgeLibrary(database_path, chunk_size=100)
    store = SQLiteEmbeddingStore(database_path)
    provider = create_embedding_provider(settings)
    indexer = DocumentEmbeddingIndexer(raw_library, store, provider)
    search = HybridKnowledgeSearch(
        raw_library,
        store,
        provider,
        HybridSearchConfig(minimum_similarity=0.25),
    )
    library = IndexedKnowledgeLibrary(raw_library, indexer, search_engine=search)
    _import_documents(root, library)
    results = library.search(SEMANTIC_QUERY, limit=1)
    return _report_result(results)


def _import_documents(root: Path, library: IndexedKnowledgeLibrary) -> None:
    """Importiert ein festes Zieldokument und einen festen Ablenkungstext."""
    target = root / "speech.md"
    distractor = root / "memory.md"
    target.write_text(TARGET_TEXT, encoding="utf-8")
    distractor.write_text(DISTRACTOR_TEXT, encoding="utf-8")
    library.import_document(str(target))
    library.import_document(str(distractor))


def _report_result(results) -> bool:
    """Meldet ausschließlich Quellmetadaten und bewertet die erwartete Rangfolge."""
    if not results or results[0].title != "speech":
        print("Expected semantic document was not ranked first. [ERROR]")
        return False
    print(f"Top source: {results[0].title}, section {results[0].chunk_index}")
    print("No document texts or vector values were logged. [OK]")
    print("Local hybrid search diagnostic passed. [OK]")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if run_diagnostic() else 1)
