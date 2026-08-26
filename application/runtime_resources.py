"""Compose local storage and controlled tool resources for the runtime."""

import sqlite3

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
from tools.changelog_status import register_latest_project_change_tool
from tools.code_quality_status import register_code_quality_status_tool
from tools.documentation_status import register_documentation_status_tool
from tools.library_status import register_local_library_status_tool
from tools.memory_status import register_local_memory_status_tool
from tools.office import register_office_tools
from tools.project_checks import register_core_project_test_tool
from tools.project_documents import register_project_document_catalog_tool
from tools.project_status import register_project_status_tool
from tools.python_release import register_python_latest_version_tool
from tools.registry import ToolRegistry
from tools.research_source import register_fixed_research_source_tool
from tools.roadmap_status import register_next_roadmap_item_tool
from tools.service_status import register_local_service_status_tool
from tools.vector_actions import register_vector_action_tools
from vector.actions import VectorActions


def _create_tool_registry(
    actions: VectorActions,
    audit_store: SQLiteToolAuditStore | None = None,
    wirepod_checker=None,
    ollama_checker=None,
    library_status_reader=None,
    memory_status_reader=None,
) -> ToolRegistry:
    """Registriert ausschließlich ausdrücklich geprüfte Produktivwerkzeuge."""
    audit_sink = audit_store.record if audit_store is not None else None
    registry = ToolRegistry(audit_sink=audit_sink)
    register_vector_action_tools(registry, actions)
    register_office_tools(registry)
    register_code_quality_status_tool(registry)
    register_documentation_status_tool(registry)
    register_latest_project_change_tool(registry)
    register_project_document_catalog_tool(registry)
    register_project_status_tool(registry)
    register_next_roadmap_item_tool(registry)
    register_fixed_research_source_tool(registry)
    register_python_latest_version_tool(registry)
    register_core_project_test_tool(registry)
    _register_optional_status_tools(
        registry,
        wirepod_checker,
        ollama_checker,
        library_status_reader,
        memory_status_reader,
    )
    return registry


def _register_optional_status_tools(
    registry,
    wirepod_checker,
    ollama_checker,
    library_status_reader,
    memory_status_reader,
) -> None:
    """Registriert lokale Statuswerkzeuge nur mit vollständigen Abhängigkeiten."""
    if (wirepod_checker is None) != (ollama_checker is None):
        raise ValueError("Local service checks must be configured together.")
    if wirepod_checker is not None:
        register_local_service_status_tool(
            registry,
            wirepod_checker,
            ollama_checker,
        )
    if library_status_reader is not None:
        register_local_library_status_tool(registry, library_status_reader)
    if memory_status_reader is not None:
        register_local_memory_status_tool(registry, memory_status_reader)


def _create_audit_store(settings) -> SQLiteToolAuditStore | None:
    """Erzeugt die optionale lokale Auditablage, ohne den Start zu blockieren."""
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


def _create_knowledge_library(
    settings,
    diagnostics=None,
) -> IndexedKnowledgeLibrary:
    """Verbindet kontrollierte Importe mit automatischer lokaler Indexierung."""
    library = SQLiteKnowledgeLibrary(settings.MEMORY_DB_PATH)
    store = SQLiteEmbeddingStore(settings.MEMORY_DB_PATH)
    provider = create_embedding_provider(settings, diagnostics)
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
    """Meldet nur Zähler, niemals Dokumentinhalte oder erzeugte Vektoren."""
    print(f"Semantic indexing: {progress.completed}/{progress.total} sections")
