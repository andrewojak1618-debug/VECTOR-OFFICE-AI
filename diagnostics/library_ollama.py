"""Run a local end-to-end check of the document library with Ollama."""

import tempfile
from pathlib import Path

from brain.agent import Agent
from brain.ollama_runtime import OllamaRuntime
from brain.providers import OllamaProvider
from config.settings import settings
from memory.library import SQLiteKnowledgeLibrary


TEST_CODE_NAME = "Nordstern 47"
TEST_QUESTION = (
    "Wie lautet der interne Codename der Dokumentbibliothek? "
    "Antworte nur mit dem Codenamen."
)


def run_diagnostic() -> bool:
    """Importiert Testwissen und prüft eine echte lokale Ollama-Antwort."""
    if not _ensure_ollama():
        return False
    with tempfile.TemporaryDirectory(prefix="vector-library-") as temp_dir:
        library = _prepare_library(Path(temp_dir))
        if library is None:
            return False
        answer = _ask_ollama(library)
        if TEST_CODE_NAME.casefold() not in answer.casefold():
            print("Ollama did not reproduce the imported fact. [ERROR]")
            return False
    print("Local document library -> Ollama diagnostic passed. [OK]")
    return True


def _ensure_ollama() -> bool:
    """Stellt den lokalen Ollama-Dienst für die Bibliotheksprüfung bereit."""
    print("Checking local Ollama service...")
    runtime = OllamaRuntime(settings.OLLAMA_HOST, settings.OLLAMA_EXECUTABLE)
    if runtime.ensure_available():
        return True
    print("Ollama library diagnostic failed: service unavailable. [ERROR]")
    return False


def _prepare_library(root: Path) -> SQLiteKnowledgeLibrary | None:
    """Erzeugt eine temporäre Bibliothek und prüft den festen lexikalischen Treffer."""
    document_path = root / "projektwissen.md"
    document_path.write_text(_test_document(), encoding="utf-8")
    library = SQLiteKnowledgeLibrary(root / "diagnostic.db")
    imported = library.import_document(document_path)
    print(
        f"Imported document {imported.document.id} "
        f"with {imported.chunk_count} section(s). [OK]"
    )
    matches = library.search(TEST_QUESTION)
    if matches and TEST_CODE_NAME in matches[0].content:
        print("Relevant library section found. [OK]")
        return library
    print("Relevant library section was not found. [ERROR]")
    return None


def _test_document() -> str:
    """Liefert das feste ungefährliche Dokumentwissen der Diagnose."""
    return (
        "# Kontrolliertes Projektwissen\n\n"
        "Der interne Codename der Dokumentbibliothek lautet "
        f"{TEST_CODE_NAME}.\n\n"
        "Dieses Testwissen darf ausschließlich lokal mit Ollama "
        "verarbeitet werden.\n"
    )


def _ask_ollama(library: SQLiteKnowledgeLibrary) -> str:
    """Stellt eine feste Frage ausschließlich an Ollama mit lokalem Dokumentkontext."""
    agent = Agent(
        OllamaProvider(settings.OLLAMA_HOST, settings.OLLAMA_MODEL),
        knowledge_library=library,
        knowledge_context_enabled=True,
    )
    answer = agent.respond(TEST_QUESTION)
    print(f"Ollama: {answer}")
    return answer


if __name__ == "__main__":
    raise SystemExit(0 if run_diagnostic() else 1)
