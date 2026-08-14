"""Application startup and dependency composition."""

from dataclasses import dataclass

from brain.agent import Agent
from brain.ollama_runtime import OllamaRuntime
from brain.providers import OllamaProvider, create_language_model
from memory.database import SQLiteMemoryStore
from memory.embedding_store import SQLiteEmbeddingStore
from memory.embeddings import create_embedding_provider
from memory.indexing import (
    DocumentEmbeddingIndexer,
    IndexedKnowledgeLibrary,
    IndexProgress,
)
from memory.library import SQLiteKnowledgeLibrary
from memory.search import HybridKnowledgeSearch, HybridSearchConfig
from vector.client import VectorClient
from vector.sdk_client import VectorSDKClient
from vector.speech import VectorSpeech
from voice.wirepod_input import WirePodTranscriptListener

from application.conversation import run_conversation, run_voice_conversation


@dataclass(frozen=True)
class RuntimeMode:
    """Normalized provider and input decisions for one application run."""

    provider: str
    fallback_provider: str
    input_mode: str
    local_voice_required: bool
    needs_ollama: bool


def get_runtime_mode(settings) -> RuntimeMode:
    """Derive normalized runtime decisions from application settings."""
    provider = settings.LLM_PROVIDER.casefold().strip()
    fallback = settings.LLM_FALLBACK_PROVIDER.casefold().strip()
    input_mode = settings.INPUT_MODE.casefold().strip()
    embedding_provider = settings.EMBEDDING_PROVIDER.casefold().strip()
    local_voice = (
        input_mode == "wirepod"
        and provider == "openai"
        and not settings.VOICE_ALLOW_CLOUD
    )
    needs_ollama = (
        provider == "ollama"
        or (provider == "openai" and fallback == "ollama")
        or local_voice
        or embedding_provider == "ollama"
    )
    return RuntimeMode(provider, fallback, input_mode, local_voice, needs_ollama)


def run_application(settings) -> None:
    """Start services, compose dependencies, and run the selected input mode."""
    _print_header(settings)
    mode = get_runtime_mode(settings)
    if not _ensure_ollama(settings, mode):
        return
    vector = _connect_vector(settings)
    if vector is None:
        return
    speech = VectorSpeech(vector, settings.TTS_VOICE, settings.TTS_VOLUME)
    agent = _create_agent(settings, mode)
    _run_input_mode(settings, mode, agent, speech)


def _print_header(settings) -> None:
    print("=" * 50)
    print(f"{settings.APP_NAME} v{settings.VERSION}")
    print("=" * 50)
    print(f"Robot:   {settings.VECTOR_NAME}")
    print(f"WirePod: {settings.WIREPOD_HOST}")


def _ensure_ollama(settings, mode: RuntimeMode) -> bool:
    if not mode.needs_ollama:
        return True
    print("\nChecking local Ollama service...")
    ready = OllamaRuntime(
        base_url=settings.OLLAMA_HOST,
        executable=settings.OLLAMA_EXECUTABLE,
    ).ensure_available()
    if ready:
        return True
    return _handle_unavailable_ollama(mode)


def _handle_unavailable_ollama(mode: RuntimeMode) -> bool:
    if mode.provider == "ollama" or mode.local_voice_required:
        print("Ollama is required as the active LLM provider. [ERROR]")
        return False
    print("Continuing with OpenAI without local fallback.")
    return True


def _connect_vector(settings) -> VectorSDKClient | None:
    print("\nChecking WirePod connection...")
    if not VectorClient(settings.WIREPOD_HOST).check_wirepod():
        print("WirePod is not reachable. [ERROR]")
        return None
    print("WirePod is online. [OK]\n")
    print("Starting Vector SDK test...")
    vector = VectorSDKClient(settings.VECTOR_SERIAL)
    return vector if vector.test_connection() else None


def _create_agent(settings, mode: RuntimeMode) -> Agent:
    print(f"\nLLM provider: {settings.LLM_PROVIDER}")
    language_model = _create_language_model(settings, mode)
    memory_store = SQLiteMemoryStore(settings.MEMORY_DB_PATH)
    library = _create_knowledge_library(settings)
    return Agent(
        language_model,
        memory_store=memory_store,
        memory_context_limit=settings.MEMORY_CONTEXT_LIMIT,
        knowledge_library=library,
        knowledge_context_limit=settings.MEMORY_CONTEXT_LIMIT,
        knowledge_context_enabled=_knowledge_enabled(settings, mode),
    )


def _create_knowledge_library(settings) -> IndexedKnowledgeLibrary:
    """Compose controlled imports with automatic local semantic indexing."""
    library = SQLiteKnowledgeLibrary(settings.MEMORY_DB_PATH)
    store = SQLiteEmbeddingStore(settings.MEMORY_DB_PATH)
    provider = create_embedding_provider(settings)
    indexer = DocumentEmbeddingIndexer(library, store, provider)
    search = HybridKnowledgeSearch(
        library,
        store,
        provider,
        HybridSearchConfig(
            lexical_weight=settings.KNOWLEDGE_LEXICAL_WEIGHT,
            semantic_weight=settings.KNOWLEDGE_SEMANTIC_WEIGHT,
            minimum_similarity=settings.KNOWLEDGE_MIN_SIMILARITY,
        ),
    )
    return IndexedKnowledgeLibrary(
        library,
        indexer,
        _print_index_progress,
        search,
    )


def _print_index_progress(progress: IndexProgress) -> None:
    """Report counts only, never document contents or generated vectors."""
    print(f"Semantic indexing: {progress.completed}/{progress.total} sections")


def _create_language_model(settings, mode: RuntimeMode):
    if not mode.local_voice_required:
        return create_language_model(settings)
    print("Voice privacy: using local Ollama (cloud disabled).")
    return OllamaProvider(settings.OLLAMA_HOST, settings.OLLAMA_MODEL)


def _knowledge_enabled(settings, mode: RuntimeMode) -> bool:
    return (
        mode.provider == "ollama"
        or mode.local_voice_required
        or settings.KNOWLEDGE_ALLOW_CLOUD
    )


def _run_input_mode(settings, mode, agent: Agent, speech: VectorSpeech) -> None:
    if mode.input_mode == "console":
        run_conversation(agent, speech)
        return
    if mode.input_mode == "wirepod":
        listener = WirePodTranscriptListener(settings.WIREPOD_HOST)
        run_voice_conversation(
            agent,
            speech,
            listener,
            listen_timeout=settings.VOICE_LISTEN_TIMEOUT,
        )
        return
    print("INPUT_MODE must be either 'console' or 'wirepod'.")
