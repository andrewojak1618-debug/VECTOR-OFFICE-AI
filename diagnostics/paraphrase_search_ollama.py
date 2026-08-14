"""Evaluate direct and paraphrased retrieval with real local embeddings."""

import tempfile
from pathlib import Path

from brain.ollama_runtime import OllamaRuntime
from config.settings import settings
from memory.embedding_store import SQLiteEmbeddingStore
from memory.embeddings import EmbeddingError, create_embedding_provider
from memory.indexing import DocumentEmbeddingIndexer, IndexedKnowledgeLibrary
from memory.library import SQLiteKnowledgeLibrary
from memory.search import HybridKnowledgeSearch, HybridSearchConfig


FACTS = (
    "Die Notabschaltung des Serverraums befindet sich hinter der blauen "
    "Abdeckung direkt neben der Eingangstür.",
    "Der Hauptschalter der Werkstatt befindet sich im grauen Schaltschrank "
    "neben dem Fenster.",
    "Die monatliche Datensicherung wird jeweils am ersten Freitag geprüft.",
)
EVALUATION_QUERIES = (
    "Wo befindet sich die Notabschaltung des Serverraums?",
    "Wo trennt man bei Gefahr die Rechneranlage vollständig vom elektrischen Netz?",
    "Wetterbericht und Kaffeepause sind heute nebensächlich. Wo trennt man bei "
    "Gefahr die Rechneranlage vollständig vom elektrischen Netz?",
)
EVALUATION_LABELS = ("direct", "paraphrase", "paraphrase-with-noise")
UNRELATED_QUERY = "Welche Temperatur benötigt ein Apfelkuchen?"


def run_diagnostic() -> bool:
    """Run the isolated paraphrase evaluation and print metadata only."""
    runtime = OllamaRuntime(settings.OLLAMA_HOST, settings.OLLAMA_EXECUTABLE)
    if not runtime.ensure_available():
        print("Local Ollama service is unavailable. [ERROR]")
        return False
    try:
        with tempfile.TemporaryDirectory(prefix="vector-paraphrase-search-") as root:
            return _run_in_directory(Path(root))
    except (EmbeddingError, OSError, ValueError) as exc:
        print(f"Paraphrase search diagnostic failed: {exc} [ERROR]")
        return False


def _run_in_directory(root: Path) -> bool:
    document_path = root / "eindeutige-fakten.md"
    document_path.write_text("\n\n".join(FACTS), encoding="utf-8")
    database_path = root / "diagnostic.db"
    raw_library = SQLiteKnowledgeLibrary(database_path, chunk_size=120)
    store = SQLiteEmbeddingStore(database_path)
    provider = create_embedding_provider(settings)
    indexer = DocumentEmbeddingIndexer(raw_library, store, provider)
    search = HybridKnowledgeSearch(
        raw_library,
        store,
        provider,
        HybridSearchConfig(minimum_similarity=0.35),
    )
    library = IndexedKnowledgeLibrary(raw_library, indexer, search_engine=search)
    document = library.import_document(str(document_path)).document
    expected = raw_library.list_chunks(document.id)[0]
    return _evaluate(library, expected.id)


def _evaluate(library: IndexedKnowledgeLibrary, expected_chunk_id: int) -> bool:
    top_ids = tuple(
        _top_chunk_id(library.search(query, limit=1))
        for query in EVALUATION_QUERIES
    )
    false_positives = len(library.search(UNRELATED_QUERY, limit=3))
    for label, chunk_id in zip(EVALUATION_LABELS, top_ids):
        state = "PASS" if chunk_id == expected_chunk_id else "FAIL"
        print(f"Case {label}: {state} (top section ID: {chunk_id})")
    print(f"Passed paraphrase cases: {sum(value == expected_chunk_id for value in top_ids)}/3")
    print(f"False positives for unrelated query: {false_positives}")
    print("No document texts, queries, or vector values were logged. [OK]")
    if all(value == expected_chunk_id for value in top_ids) and false_positives == 0:
        print("Local paraphrase search diagnostic passed. [OK]")
        return True
    print("Local paraphrase search diagnostic did not meet its thresholds. [ERROR]")
    return False


def _top_chunk_id(results) -> int | None:
    return results[0].id if results else None


if __name__ == "__main__":
    raise SystemExit(0 if run_diagnostic() else 1)
