"""Application startup and dependency composition."""

import sqlite3
from dataclasses import dataclass

from brain.agent import Agent
from brain.ollama_runtime import OllamaRuntime
from brain.providers import OllamaProvider, create_language_model
from brain.reflection import ReflectionPolicy
from diagnostics.events import DiagnosticLevel, StructuredDiagnosticReporter
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
from tools.audit_store import SQLiteToolAuditStore
from tools.office import register_office_tools
from tools.project_status import register_project_status_tool
from tools.registry import ToolRegistry
from tools.vector_actions import register_vector_action_tools
from vector.actions import VectorActions
from vector.behavior_control import BehaviorControl
from vector.client import VectorClient
from vector.sdk_client import VectorSDKClient
from vector.speech import VectorSpeech
from vector.speech_factory import create_speech_output
from voice.wirepod_input import WirePodTranscriptListener

from application.conversation import run_conversation, run_voice_conversation
from application.connection_supervisor import ConnectionSupervisor


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
    diagnostics = _create_diagnostics(settings)
    connections = ConnectionSupervisor(diagnostics)
    _emit_runtime_start(diagnostics, mode)
    vector = _prepare_vector(settings, mode, diagnostics, connections)
    if vector is None:
        return
    speech = create_speech_output(settings, vector)
    actions = VectorActions(vector, settings.ROBOT_ACTION_TIMEOUT)
    audit_store = _create_audit_store(settings)
    registry = _create_tool_registry(actions, audit_store)
    agent = _create_agent(settings, mode, registry, diagnostics)
    _run_input_mode(settings, mode, agent, speech, diagnostics, connections)
    diagnostics.emit(
        DiagnosticLevel.INFO,
        "application",
        "runtime.stopped",
        status="completed",
    )


def _prepare_vector(
    settings,
    mode,
    diagnostics,
    connections,
) -> VectorSDKClient | None:
    if not _ensure_ollama(settings, mode, diagnostics, connections):
        _emit_startup_blocked(diagnostics, "ollama-unavailable")
        return None
    vector = _connect_vector(settings, BehaviorControl(), connections)
    if vector is None:
        _emit_startup_blocked(diagnostics, "vector-unavailable")
    return vector


def _emit_startup_blocked(diagnostics, reason_code: str) -> None:
    diagnostics.emit(
        DiagnosticLevel.ERROR,
        "application",
        "startup.blocked",
        reason_code=reason_code,
    )


def _create_diagnostics(settings) -> StructuredDiagnosticReporter:
    """Create the bounded local runtime diagnostic sink."""
    return StructuredDiagnosticReporter(
        getattr(settings, "DIAGNOSTICS_PATH", "data/diagnostics/events.jsonl"),
        getattr(settings, "DIAGNOSTICS_ENABLED", True),
        getattr(settings, "DIAGNOSTICS_MAX_BYTES", 1_000_000),
    )


def _emit_runtime_start(
    diagnostics: StructuredDiagnosticReporter,
    mode: RuntimeMode,
) -> None:
    diagnostics.emit(
        DiagnosticLevel.INFO,
        "application",
        "runtime.started",
        provider=mode.provider,
        fallback=mode.fallback_provider,
        input_mode=mode.input_mode,
        local=mode.local_voice_required,
    )


def _print_header(settings) -> None:
    print("=" * 50)
    print(f"{settings.APP_NAME} v{settings.VERSION}")
    print("=" * 50)
    print(f"Robot:   {settings.VECTOR_NAME}")
    print(f"WirePod: {settings.WIREPOD_HOST}")


def _ensure_ollama(settings, mode: RuntimeMode, diagnostics, connections) -> bool:
    if not mode.needs_ollama:
        return True
    print("\nChecking local Ollama service...")
    runtime = OllamaRuntime(
        base_url=settings.OLLAMA_HOST,
        executable=settings.OLLAMA_EXECUTABLE,
    )
    ready = runtime.ensure_available()
    if ready and mode.local_voice_required:
        ready = runtime.preload_model(
            settings.OLLAMA_MODEL,
            settings.LLM_REQUEST_TIMEOUT,
        )
    connections.observe("ollama", ready)
    if ready:
        diagnostics.emit(
            DiagnosticLevel.INFO,
            "ollama",
            "service.ready",
            local=True,
            status="available",
        )
        return True
    allowed = _handle_unavailable_ollama(mode)
    diagnostics.emit(
        DiagnosticLevel.WARNING if allowed else DiagnosticLevel.ERROR,
        "ollama",
        "service.unavailable",
        local=True,
        status="fallback-allowed" if allowed else "required",
    )
    return allowed


def _handle_unavailable_ollama(mode: RuntimeMode) -> bool:
    if mode.provider == "ollama" or mode.local_voice_required:
        print("Ollama is required as the active LLM provider. [ERROR]")
        return False
    print("Continuing with OpenAI without local fallback.")
    return True


def _connect_vector(
    settings,
    behavior_control: BehaviorControl | None = None,
    connections: ConnectionSupervisor | None = None,
) -> VectorSDKClient | None:
    print("\nChecking WirePod connection...")
    client = VectorClient(settings.WIREPOD_HOST)
    ready = _wait_for_connection(connections, "wirepod", client.check_wirepod)
    if not ready:
        print("WirePod is not reachable. [ERROR]")
        return None
    print("WirePod is online. [OK]\n")
    print("Starting Vector SDK test...")
    vector = VectorSDKClient(settings.VECTOR_SERIAL, behavior_control)
    connected = _wait_for_connection(
        connections,
        "vector-sdk",
        vector.test_connection,
    )
    return vector if connected else None


def _wait_for_connection(connections, service, health_check) -> bool:
    if connections is None:
        return health_check()
    return connections.wait_until_available(service, health_check, max_attempts=3)


def _create_agent(
    settings,
    mode: RuntimeMode,
    tool_registry: ToolRegistry | None = None,
    diagnostics: StructuredDiagnosticReporter | None = None,
) -> Agent:
    print(f"\nLLM provider: {settings.LLM_PROVIDER}")
    language_model = _create_language_model(settings, mode, diagnostics)
    memory_store = SQLiteMemoryStore(settings.MEMORY_DB_PATH)
    library = _create_knowledge_library(settings)
    return Agent(
        language_model,
        memory_store=memory_store,
        memory_context_limit=settings.MEMORY_CONTEXT_LIMIT,
        knowledge_library=library,
        knowledge_context_limit=settings.MEMORY_CONTEXT_LIMIT,
        knowledge_context_enabled=_knowledge_enabled(settings, mode),
        tool_registry=tool_registry or ToolRegistry(),
        reflection_policy=ReflectionPolicy(settings.REFLECTION_ENABLED),
    )


def _create_tool_registry(
    actions: VectorActions,
    audit_store: SQLiteToolAuditStore | None = None,
) -> ToolRegistry:
    """Register only explicitly reviewed production robot tools."""
    audit_sink = audit_store.record if audit_store is not None else None
    registry = ToolRegistry(audit_sink=audit_sink)
    register_vector_action_tools(registry, actions)
    register_office_tools(registry)
    register_project_status_tool(registry)
    return registry


def _create_audit_store(settings) -> SQLiteToolAuditStore | None:
    """Create optional local persistence without blocking application startup."""
    if not settings.TOOL_AUDIT_ENABLED:
        return None
    try:
        return SQLiteToolAuditStore(
            settings.MEMORY_DB_PATH,
            settings.TOOL_AUDIT_RETENTION_DAYS,
            settings.TOOL_AUDIT_MAX_ENTRIES,
        )
    except (OSError, sqlite3.Error):
        print("Local tool audit is unavailable. Continuing without persistence.")
        return None


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


def _create_language_model(settings, mode: RuntimeMode, diagnostics=None):
    if not mode.local_voice_required:
        return create_language_model(settings, diagnostics)
    print("Application voice model: local Ollama (cloud disabled here).")
    print("WirePod Knowledge Graph privacy must be configured separately.")
    return OllamaProvider(
        settings.OLLAMA_HOST,
        settings.OLLAMA_MODEL,
        timeout=getattr(settings, "LLM_REQUEST_TIMEOUT", 120.0),
        max_attempts=getattr(settings, "LLM_MAX_ATTEMPTS", 2),
        retry_delay=getattr(settings, "LLM_RETRY_DELAY", 0.5),
        temperature=getattr(settings, "OLLAMA_TEMPERATURE", 0.25),
        max_output_tokens=getattr(settings, "OLLAMA_MAX_OUTPUT_TOKENS", 64),
        context_window=getattr(settings, "OLLAMA_CONTEXT_WINDOW", 4_096),
        diagnostics=diagnostics,
    )


def _knowledge_enabled(settings, mode: RuntimeMode) -> bool:
    return (
        mode.provider == "ollama"
        or mode.local_voice_required
        or settings.KNOWLEDGE_ALLOW_CLOUD
    )


def _run_input_mode(
    settings,
    mode,
    agent: Agent,
    speech: VectorSpeech,
    diagnostics: StructuredDiagnosticReporter,
    connections: ConnectionSupervisor,
) -> None:
    _report_input_started(diagnostics, mode)
    if mode.input_mode == "console":
        run_conversation(agent, speech)
        return
    if mode.input_mode == "wirepod":
        _run_wirepod_input(settings, agent, speech, connections)
        return
    print("INPUT_MODE must be either 'console' or 'wirepod'.")
    diagnostics.emit(
        DiagnosticLevel.ERROR,
        "conversation",
        "input.invalid",
        input_mode=mode.input_mode,
        reason_code="unsupported-input-mode",
    )


def _report_input_started(diagnostics, mode) -> None:
    diagnostics.emit(
        DiagnosticLevel.INFO,
        "conversation",
        "input.started",
        input_mode=mode.input_mode,
        cloud_allowed=not mode.local_voice_required,
    )


def _run_wirepod_input(settings, agent, speech, connections) -> None:
    listener = WirePodTranscriptListener(settings.WIREPOD_HOST)
    run_voice_conversation(
        agent,
        speech,
        listener,
        listen_timeout=settings.VOICE_LISTEN_TIMEOUT,
        connections=connections,
    )
