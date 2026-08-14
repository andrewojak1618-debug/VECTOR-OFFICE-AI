"""Coordinate automatic local document indexing and safe reindexing."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from memory.embedding_store import (
    ChunkEmbedding,
    SQLiteEmbeddingStore,
    StoredEmbedding,
)
from memory.embeddings import (
    EmbeddingError,
    EmbeddingModelInfo,
    EmbeddingProvider,
    EmbeddingText,
)
from memory.exporting import LocalDataExporter
from memory.library import SQLiteKnowledgeLibrary
from memory.models import (
    DocumentIndexStatus,
    DocumentImportResult,
    IndexingResult,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    StaleEmbeddingStatus,
)


DEFAULT_INDEX_BATCH_SIZE = 32


@dataclass(frozen=True)
class IndexProgress:
    """Describe completed local embedding work without exposing document text."""

    completed: int
    total: int


ProgressCallback = Callable[[IndexProgress], None]


class KnowledgeSearch(Protocol):
    """Provide ranked document sections for a normalized query."""

    def search(self, query: str, limit: int = 5) -> tuple[KnowledgeChunk, ...]:
        """Return at most ``limit`` ranked document sections."""
        ...


class DocumentEmbeddingIndexer:
    """Generate only required vectors and persist them in one transaction."""

    def __init__(
        self,
        library: SQLiteKnowledgeLibrary,
        store: SQLiteEmbeddingStore,
        provider: EmbeddingProvider,
        batch_size: int = DEFAULT_INDEX_BATCH_SIZE,
    ):
        if batch_size < 1:
            raise ValueError("Embedding batch size must be at least 1.")
        self.library = library
        self.store = store
        self.provider = provider
        self.batch_size = batch_size

    def index_document(
        self,
        document_id: int,
        *,
        force: bool = False,
        progress: ProgressCallback | None = None,
    ) -> IndexingResult:
        """Index missing or stale chunks, optionally forcing a full refresh."""
        chunks = self.library.list_chunks(document_id)
        if not chunks:
            raise ValueError("Document has no indexable chunks.")
        model = self.provider.ensure_model_available()
        model_changed = self.store.has_other_model_identity(document_id, model)
        targets = self._target_chunks(document_id, chunks, model, force)
        generated = self._generate_embeddings(targets, progress)
        # No database write happens before all provider batches succeed.
        self.store.save_many(generated, model)
        return self._result(document_id, chunks, targets, model_changed, force)

    def _target_chunks(
        self,
        document_id: int,
        chunks: tuple[KnowledgeChunk, ...],
        model: EmbeddingModelInfo,
        force: bool,
    ) -> tuple[KnowledgeChunk, ...]:
        if force:
            return chunks
        pending = set(self.store.pending_chunk_ids(document_id, model))
        return tuple(chunk for chunk in chunks if chunk.id in pending)

    def _generate_embeddings(
        self,
        targets: tuple[KnowledgeChunk, ...],
        progress: ProgressCallback | None,
    ) -> tuple[ChunkEmbedding, ...]:
        generated: list[ChunkEmbedding] = []
        for offset in range(0, len(targets), self.batch_size):
            batch = targets[offset:offset + self.batch_size]
            generated.extend(self._embed_batch(batch))
            if progress is not None:
                progress(IndexProgress(len(generated), len(targets)))
        return tuple(generated)

    def _embed_batch(
        self,
        chunks: tuple[KnowledgeChunk, ...],
    ) -> tuple[ChunkEmbedding, ...]:
        texts = tuple(EmbeddingText(chunk.content) for chunk in chunks)
        results = self.provider.embed_many(texts)
        if len(results) != len(chunks):
            raise ValueError("Embedding provider returned an incomplete batch.")
        return tuple(
            ChunkEmbedding(chunk.id, result)
            for chunk, result in zip(chunks, results)
        )

    @staticmethod
    def _result(
        document_id: int,
        chunks: tuple[KnowledgeChunk, ...],
        targets: tuple[KnowledgeChunk, ...],
        model_changed: bool,
        force: bool,
    ) -> IndexingResult:
        indexed = len(targets)
        return IndexingResult(
            document_id=document_id,
            total_chunks=len(chunks),
            indexed_chunks=indexed,
            skipped_chunks=len(chunks) - indexed,
            model_changed=model_changed,
            forced=force,
        )


class IndexedKnowledgeLibrary:
    """Add automatic local vector indexing to the controlled library."""

    def __init__(
        self,
        library: SQLiteKnowledgeLibrary,
        indexer: DocumentEmbeddingIndexer,
        progress: ProgressCallback | None = None,
        search_engine: KnowledgeSearch | None = None,
    ):
        self.library = library
        self.indexer = indexer
        self.progress = progress
        self.search_engine = search_engine
        self.last_indexing_result: IndexingResult | None = None
        self.last_reindex_results: tuple[IndexingResult, ...] = ()

    def import_document(self, source_path: str) -> DocumentImportResult:
        """Import a document and incrementally index its current sections."""
        result = self.library.import_document(source_path)
        self.last_indexing_result = self.indexer.index_document(
            result.document.id,
            progress=self.progress,
        )
        return result

    def reindex_document(self, document_id: int) -> IndexingResult:
        """Force generation of every current vector for one document."""
        result = self.indexer.index_document(
            document_id,
            force=True,
            progress=self.progress,
        )
        self.last_indexing_result = result
        return result

    def reindex_all(self) -> tuple[IndexingResult, ...]:
        """Force a local semantic rebuild for every imported document."""
        results = tuple(
            self.indexer.index_document(
                document.id,
                force=True,
                progress=self.progress,
            )
            for document in self.library.list_all_documents()
        )
        self.last_reindex_results = results
        self.last_indexing_result = results[-1] if results else None
        return results

    def search(self, query: str, limit: int = 5) -> tuple[KnowledgeChunk, ...]:
        """Use hybrid retrieval when configured, otherwise lexical retrieval."""
        if self.search_engine is None:
            return self.library.search(query, limit)
        return self.search_engine.search(query, limit)

    def list_documents(self, limit: int = 50) -> tuple[KnowledgeDocument, ...]:
        """Return imported document metadata."""
        return self.library.list_documents(limit)

    def list_document_versions(
        self,
        document_id: int,
    ) -> tuple[KnowledgeDocumentVersion, ...]:
        """Return the immutable metadata history for one document."""
        return self.library.list_document_versions(document_id)

    def list_document_statuses(self) -> tuple[DocumentIndexStatus, ...]:
        """Return a complete inventory with active-model vector status."""
        try:
            model = self.indexer.provider.ensure_model_available()
        except EmbeddingError:
            return tuple(
                self._offline_document_status(document)
                for document in self.library.list_all_documents()
            )
        return tuple(
            self._document_status(document, model)
            for document in self.library.list_all_documents()
        )

    def list_stale_vectors(self) -> tuple[StaleEmbeddingStatus, ...]:
        """Return stale vector metadata for the active embedding model."""
        model = self.indexer.provider.ensure_model_available()
        return tuple(
            self._stale_status(document.id, embedding)
            for document in self.library.list_all_documents()
            for embedding in self.indexer.store.list_stale_for_document(
                document.id,
                model,
            )
        )

    def export_library_metadata(self, destination: str | Path) -> Path:
        """Export sanitized document, version, and vector metadata."""
        statuses = self.list_document_statuses()
        versions = {
            status.document.id: self.list_document_versions(status.document.id)
            for status in statuses
        }
        return LocalDataExporter().export_library(destination, statuses, versions)

    def forget_document(self, document_id: int) -> bool:
        """Delete a document, its chunks, and cascaded embeddings."""
        deleted = self.library.forget_document(document_id)
        if deleted:
            self._verify_deleted(document_id)
        return deleted

    def _document_status(
        self,
        document: KnowledgeDocument,
        model: EmbeddingModelInfo,
    ) -> DocumentIndexStatus:
        embeddings = self.indexer.store.list_for_document(document.id)
        stale = self.indexer.store.list_stale_for_document(document.id, model)
        return DocumentIndexStatus(
            document=document,
            version_count=len(self.library.list_document_versions(document.id)),
            chunk_count=len(self.library.list_chunks(document.id)),
            model_name=model.model_name,
            model_version=model.model_version,
            dimension=model.dimension,
            current_vectors=len(embeddings) - len(stale),
            stale_vectors=len(stale),
        )

    @staticmethod
    def _stale_status(
        document_id: int,
        embedding: StoredEmbedding,
    ) -> StaleEmbeddingStatus:
        return StaleEmbeddingStatus(
            document_id=document_id,
            chunk_id=embedding.chunk_id,
            model_name=embedding.model_name,
            model_version=embedding.model_version,
            dimension=embedding.dimension,
            updated_at=embedding.updated_at,
        )

    def _offline_document_status(
        self,
        document: KnowledgeDocument,
    ) -> DocumentIndexStatus:
        embeddings = self.indexer.store.list_for_document(document.id)
        if embeddings:
            latest = max(embeddings, key=lambda item: item.id)
            model = EmbeddingModelInfo(
                latest.model_name,
                latest.model_version,
                latest.dimension,
            )
            return self._document_status(document, model)
        return DocumentIndexStatus(
            document=document,
            version_count=len(self.library.list_document_versions(document.id)),
            chunk_count=len(self.library.list_chunks(document.id)),
            model_name=self.indexer.provider.model_name,
            model_version="unavailable",
            dimension=self.indexer.provider.dimension,
            current_vectors=0,
            stale_vectors=0,
        )

    def _verify_deleted(self, document_id: int) -> None:
        remains = (
            self.library.document_exists(document_id)
            or bool(self.library.list_document_versions(document_id))
            or bool(self.indexer.store.list_for_document(document_id))
        )
        if remains:
            raise RuntimeError("Document deletion could not be verified.")
