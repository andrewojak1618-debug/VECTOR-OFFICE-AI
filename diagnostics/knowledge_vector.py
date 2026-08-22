"""Test semantic project knowledge through local Ollama and physical Vector."""

import re
import tempfile
from pathlib import Path

from brain.agent import Agent
from brain.ollama_runtime import OllamaRuntime
from brain.providers import OllamaProvider
from config.settings import BASE_DIR, settings
from memory.embedding_store import SQLiteEmbeddingStore
from memory.embeddings import EmbeddingError, create_embedding_provider
from memory.indexing import DocumentEmbeddingIndexer, IndexedKnowledgeLibrary
from memory.library import SQLiteKnowledgeLibrary
from memory.search import HybridKnowledgeSearch, HybridSearchConfig
from vector.client import VectorClient
from vector.sdk_client import VectorSDKClient
from vector.speech import VectorSpeech


TEST_DOCUMENT = BASE_DIR / "docs" / "paraphrase-evaluation.md"
TEST_QUESTION = (
    "Welcher produktive Mindestähnlichkeitswert bestand laut Dokument alle drei "
    "relevanten Fragen, während der strengere Fehlversuch verworfen wurde? "
    "Nenne nur den erfolgreichen Wert und antworte auf Deutsch in höchstens "
    "zwei kurzen Sätzen."
)
EXPECTED_VALUES = ("0,35", "0.35")


def run_diagnostic() -> bool:
    """Prüft den vollständigen lokalen Pfad vom Wissen zur physischen Sprachausgabe."""
    if not _valid_document() or not _ensure_ollama():
        return False
    try:
        answer = _prepare_answer()
    except (EmbeddingError, OSError, RuntimeError, ValueError) as exc:
        print(f"Knowledge path failed: {exc} [ERROR]")
        return False
    if answer is None:
        return False
    vector = _connect_vector()
    if vector is None or not _speak(vector, answer):
        return False
    print("Semantic knowledge -> Ollama -> German TTS -> Vector passed. [OK]")
    print("Please rate pronunciation, volume, and answer quality by listening.")
    return True


def _valid_document() -> bool:
    """Prüft das festgelegte ungefährliche Projektdokument vor dem Import."""
    if TEST_DOCUMENT.is_file():
        return True
    print(f"Safe project document is missing: {TEST_DOCUMENT} [ERROR]")
    return False


def _ensure_ollama() -> bool:
    """Stellt Ollama für Einbettung und lokale Antworterzeugung bereit."""
    print("Checking local Ollama service...")
    runtime = OllamaRuntime(settings.OLLAMA_HOST, settings.OLLAMA_EXECUTABLE)
    if runtime.ensure_available():
        return True
    print("Ollama is unavailable. [ERROR]")
    return False


def _prepare_answer() -> str | None:
    """Durchläuft Import, semantischen Abruf und begrenzte lokale Antworterzeugung."""
    with tempfile.TemporaryDirectory(prefix="vector-knowledge-path-") as root:
        library, search = _prepare_library(Path(root))
        imported = library.import_document(str(TEST_DOCUMENT))
        print(f"Imported {imported.document.title}: {imported.chunk_count} sections [OK]")
        if not _report_semantic_match(search):
            return None
        answer = _generate_local_answer(library)
        print(f"Ollama answer ({_sentence_count(answer)} sentence(s)): {answer}")
        if not _answer_has_expected_fact(answer):
            print("Ollama answer missed the expected knowledge value. [ERROR]")
            return None
        return answer


def _prepare_library(
    root: Path,
) -> tuple[IndexedKnowledgeLibrary, HybridKnowledgeSearch]:
    """Baut die temporäre lokal eingebettete Hybridbibliothek auf."""
    database_path = root / "diagnostic.db"
    raw_library = SQLiteKnowledgeLibrary(database_path)
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
    return library, search


def _report_semantic_match(search: HybridKnowledgeSearch) -> bool:
    """Prüft den semantischen Treffer und zeigt nur Quelle, Abschnitt und Wert."""
    matches = search.search_with_scores(TEST_QUESTION, limit=1)
    if not matches or matches[0].semantic_similarity is None:
        print("No semantic project knowledge match found. [ERROR]")
        return False
    match = matches[0]
    print(
        f"Source: {Path(match.chunk.source_path).name}, "
        f"section {match.chunk.chunk_index}"
    )
    print(
        f"Combined score: {match.score:.3f}; "
        f"semantic similarity: {match.semantic_similarity:.3f} [OK]"
    )
    return True


def _generate_local_answer(library: IndexedKnowledgeLibrary) -> str:
    """Erzeugt mit Ollama höchstens zwei Sätze aus lokalem Dokumentwissen."""
    agent = Agent(
        OllamaProvider(
            settings.OLLAMA_HOST,
            settings.OLLAMA_MODEL,
            temperature=0.0,
        ),
        knowledge_library=library,
        knowledge_context_limit=2,
        knowledge_context_enabled=True,
    )
    return _limit_to_two_sentences(agent.respond(TEST_QUESTION))


def _limit_to_two_sentences(answer: str) -> str:
    """Begrenzt eine Diagnoseantwort auf ihre ersten zwei vollständigen Sätze."""
    sentences = tuple(
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", answer.strip())
        if sentence.strip()
    )
    return " ".join(sentences[:2])


def _sentence_count(answer: str) -> int:
    """Zählt die erkennbaren nicht leeren Sätze einer Diagnoseantwort."""
    return len(tuple(part for part in re.split(r"[.!?]+", answer) if part.strip()))


def _answer_has_expected_fact(answer: str) -> bool:
    """Prüft die feste erwartete Zahl in deutscher oder technischer Schreibweise."""
    return bool(answer.strip()) and any(value in answer for value in EXPECTED_VALUES)


def _connect_vector() -> VectorSDKClient | None:
    """Prüft WirePod und verbindet Vector für die physische Abnahme."""
    print("Checking WirePod and Vector SDK...")
    if not VectorClient(settings.WIREPOD_HOST).check_wirepod():
        print("WirePod is unavailable. [ERROR]")
        return None
    vector = VectorSDKClient(settings.VECTOR_SERIAL)
    return vector if vector.test_connection() else None


def _speak(vector: VectorSDKClient, answer: str) -> bool:
    """Spricht die begrenzte lokale Antwort mit der deutschen TTS-Konfiguration."""
    print(f"German TTS voice: {settings.TTS_VOICE}; volume: {settings.TTS_VOLUME}")
    speech = VectorSpeech(vector, settings.TTS_VOICE, settings.TTS_VOLUME)
    if speech.say(answer):
        return True
    print("Vector could not play the local knowledge answer. [ERROR]")
    return False


if __name__ == "__main__":
    raise SystemExit(0 if run_diagnostic() else 1)
