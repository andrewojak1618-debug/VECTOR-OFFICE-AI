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
    """Import test knowledge and verify a real local Ollama response."""
    print("Checking local Ollama service...")
    runtime = OllamaRuntime(
        base_url=settings.OLLAMA_HOST,
        executable=settings.OLLAMA_EXECUTABLE,
    )
    if not runtime.ensure_available():
        print("Ollama library diagnostic failed: service unavailable. [ERROR]")
        return False

    with tempfile.TemporaryDirectory(prefix="vector-library-") as temp_dir:
        root = Path(temp_dir)
        document_path = root / "projektwissen.md"
        document_path.write_text(
            "# Kontrolliertes Projektwissen\n\n"
            "Der interne Codename der Dokumentbibliothek lautet "
            f"{TEST_CODE_NAME}.\n\n"
            "Dieses Testwissen darf ausschließlich lokal mit Ollama "
            "verarbeitet werden.\n",
            encoding="utf-8",
        )

        library = SQLiteKnowledgeLibrary(root / "diagnostic.db")
        imported = library.import_document(document_path)
        print(
            f"Imported document {imported.document.id} "
            f"with {imported.chunk_count} section(s). [OK]"
        )

        matches = library.search(TEST_QUESTION)
        if not matches or TEST_CODE_NAME not in matches[0].content:
            print("Relevant library section was not found. [ERROR]")
            return False
        print("Relevant library section found. [OK]")

        agent = Agent(
            OllamaProvider(
                base_url=settings.OLLAMA_HOST,
                model=settings.OLLAMA_MODEL,
            ),
            knowledge_library=library,
            knowledge_context_enabled=True,
        )
        answer = agent.respond(TEST_QUESTION)
        print(f"Ollama: {answer}")

        if TEST_CODE_NAME.casefold() not in answer.casefold():
            print("Ollama did not reproduce the imported fact. [ERROR]")
            return False

    print("Local document library -> Ollama diagnostic passed. [OK]")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if run_diagnostic() else 1)
