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
    """Answer from README knowledge with Ollama and speak via Vector."""
    document_path = BASE_DIR / "README.md"
    if not document_path.is_file():
        print(f"Project document is missing: {document_path} [ERROR]")
        return False

    print("Checking local Ollama service...")
    runtime = OllamaRuntime(
        base_url=settings.OLLAMA_HOST,
        executable=settings.OLLAMA_EXECUTABLE,
    )
    if not runtime.ensure_available():
        print("Ollama is unavailable. [ERROR]")
        return False

    with tempfile.TemporaryDirectory(prefix="vector-readme-") as temp_dir:
        library = SQLiteKnowledgeLibrary(Path(temp_dir) / "diagnostic.db")
        imported = library.import_document(document_path)
        print(
            f"Imported {imported.document.title} with "
            f"{imported.chunk_count} section(s). [OK]"
        )

        matches = library.search(TEST_QUESTION)
        if not matches:
            print("No relevant README section found. [ERROR]")
            return False
        print(
            f"Using README section {matches[0].chunk_index} "
            "as local knowledge. [OK]"
        )

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

    print("Checking WirePod connection...")
    if not VectorClient(settings.WIREPOD_HOST).check_wirepod():
        print("WirePod is unavailable. [ERROR]")
        return False

    vector = VectorSDKClient(settings.VECTOR_SERIAL)
    if not vector.test_connection():
        print("Vector SDK connection failed. [ERROR]")
        return False

    speech = VectorSpeech(
        vector,
        voice=settings.TTS_VOICE,
        volume=settings.TTS_VOLUME,
    )
    if not speech.say(answer):
        print("Vector could not play the Ollama response. [ERROR]")
        return False

    print("README -> library -> Ollama -> Vector speech passed. [OK]")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if run_diagnostic() else 1)
