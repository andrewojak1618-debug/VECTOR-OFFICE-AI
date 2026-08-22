"""Test a real project document through Ollama and physical Vector speech."""

import tempfile
from pathlib import Path

from brain.agent import Agent
from brain.ollama_runtime import OllamaRuntime
from brain.providers import OllamaProvider
from config.settings import BASE_DIR, settings
from memory.library import SQLiteKnowledgeLibrary
from vector.client import VectorClient
from vector.sdk_client import VectorSDKClient
from vector.speech import VectorSpeech


TEST_QUESTION = (
    "Was ist die langfristige Vision von Vector Office AI? "
    "Antworte auf Deutsch in höchstens zwei kurzen Sätzen."
)


def run_diagnostic() -> bool:
    """Beantwortet README-Wissen mit Ollama und spricht es über Vector."""
    document_path = BASE_DIR / "README.md"
    if not _valid_document(document_path) or not _ensure_ollama():
        return False
    answer = _answer_from_document(document_path)
    if answer is None:
        return False
    vector = _connect_vector()
    if vector is None:
        return False
    if not _speak(vector, answer):
        return False
    print("README -> library -> Ollama -> Vector speech passed. [OK]")
    return True


def _valid_document(document_path: Path) -> bool:
    """Prüft das fest vorgegebene Projektdokument vor dem Import."""
    if document_path.is_file():
        return True
    print(f"Project document is missing: {document_path} [ERROR]")
    return False


def _ensure_ollama() -> bool:
    """Stellt den lokalen Ollama-Dienst für den physischen Wissenspfad bereit."""
    print("Checking local Ollama service...")
    runtime = OllamaRuntime(settings.OLLAMA_HOST, settings.OLLAMA_EXECUTABLE)
    if runtime.ensure_available():
        return True
    print("Ollama is unavailable. [ERROR]")
    return False


def _answer_from_document(document_path: Path) -> str | None:
    """Importiert temporär das Dokument und erzeugt daraus lokal eine Antwort."""
    with tempfile.TemporaryDirectory(prefix="vector-readme-") as temp_dir:
        library = SQLiteKnowledgeLibrary(Path(temp_dir) / "diagnostic.db")
        imported = library.import_document(document_path)
        print(
            f"Imported {imported.document.title} with "
            f"{imported.chunk_count} section(s). [OK]"
        )
        if not _report_match(library):
            return None
        answer = _build_agent(library).respond(TEST_QUESTION)
        print(f"Ollama: {answer}")
        return answer


def _report_match(library: SQLiteKnowledgeLibrary) -> bool:
    """Bestätigt einen passenden Abschnitt und meldet nur dessen Nummer."""
    matches = library.search(TEST_QUESTION)
    if not matches:
        print("No relevant README section found. [ERROR]")
        return False
    print(
        f"Using README section {matches[0].chunk_index} "
        "as local knowledge. [OK]"
    )
    return True


def _build_agent(library: SQLiteKnowledgeLibrary) -> Agent:
    """Erzeugt einen lokalen Ollama-Agenten mit freigegebenem Dokumentkontext."""
    return Agent(
        OllamaProvider(settings.OLLAMA_HOST, settings.OLLAMA_MODEL),
        knowledge_library=library,
        knowledge_context_enabled=True,
    )


def _connect_vector() -> VectorSDKClient | None:
    """Prüft WirePod und verbindet den physischen Vector über die SDK-Grenze."""
    print("Checking WirePod connection...")
    if not VectorClient(settings.WIREPOD_HOST).check_wirepod():
        print("WirePod is unavailable. [ERROR]")
        return None
    vector = VectorSDKClient(settings.VECTOR_SERIAL)
    if vector.test_connection():
        return vector
    print("Vector SDK connection failed. [ERROR]")
    return None


def _speak(vector: VectorSDKClient, answer: str) -> bool:
    """Spricht die lokale Wissensantwort mit der konfigurierten deutschen Stimme."""
    speech = VectorSpeech(vector, settings.TTS_VOICE, settings.TTS_VOLUME)
    if speech.say(answer):
        return True
    print("Vector could not play the Ollama response. [ERROR]")
    return False


if __name__ == "__main__":
    raise SystemExit(0 if run_diagnostic() else 1)
