"""Coordinate automatic local document indexing and safe reindexing."""

from collections.abc import Callable
from dataclasses import dataclass

from memory.embedding_store import (
    ChunkEmbedding,
    SQLiteEmbeddingStore,
)
from memory.embeddings import EmbeddingModelInfo, EmbeddingProvider, EmbeddingText
from memory.library import SQLiteKnowledgeLibrary
from memory.models import DocumentImportResult, IndexingResult, KnowledgeChunk


DEFAULT_INDEX_BATCH_SIZE = 32


@dataclass(frozen=True)
class IndexProgress:
    """Describe completed local embedding work without exposing document text."""

    completed: int
    total: int


ProgressCallback = Callable[[IndexProgress], None]


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
    ):
        self.library = library
        self.indexer = indexer
        self.progress = progress
        self.last_indexing_result: IndexingResult | None = None

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

    def search(self, query: str, limit: int = 5):
        """Delegate lexical retrieval until semantic retrieval is introduced."""
        return self.library.search(query, limit)

    def list_documents(self, limit: int = 50):
        """Return imported document metadata."""
        return self.library.list_documents(limit)

    def forget_document(self, document_id: int) -> bool:
        """Delete a document, its chunks, and cascaded embeddings."""
        return self.library.forget_document(document_id)
