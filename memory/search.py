"""Hybrid lexical and local semantic retrieval for document knowledge."""

import math
from dataclasses import dataclass

from memory.embedding_store import SQLiteEmbeddingStore
from memory.embeddings import (
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingText,
    EmbeddingVector,
)
from memory.library import SQLiteKnowledgeLibrary
from memory.models import KnowledgeChunk


DEFAULT_LEXICAL_WEIGHT = 0.45
DEFAULT_SEMANTIC_WEIGHT = 0.55
DEFAULT_MIN_SIMILARITY = 0.35
DEFAULT_CANDIDATE_LIMIT = 200


def cosine_similarity(left: EmbeddingVector, right: EmbeddingVector) -> float:
    """Return clamped cosine similarity for two equal-dimension vectors."""
    if left.dimension != right.dimension:
        raise ValueError("Embedding dimensions must match for cosine similarity.")
    dot_product = sum(a * b for a, b in zip(left.values, right.values))
    left_norm = math.sqrt(sum(value * value for value in left.values))
    right_norm = math.sqrt(sum(value * value for value in right.values))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    similarity = dot_product / (left_norm * right_norm)
    return max(-1.0, min(1.0, similarity))


@dataclass(frozen=True)
class HybridSearchConfig:
    """Configure deterministic lexical and semantic document ranking."""

    lexical_weight: float = DEFAULT_LEXICAL_WEIGHT
    semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT
    minimum_similarity: float = DEFAULT_MIN_SIMILARITY
    candidate_limit: int = DEFAULT_CANDIDATE_LIMIT

    def __post_init__(self) -> None:
        weights = (self.lexical_weight, self.semantic_weight)
        if not all(math.isfinite(weight) for weight in weights):
            raise ValueError("Hybrid search weights must be finite.")
        if self.lexical_weight < 0 or self.semantic_weight < 0:
            raise ValueError("Hybrid search weights must not be negative.")
        if self.lexical_weight + self.semantic_weight <= 0:
            raise ValueError("At least one hybrid search weight must be positive.")
        if not math.isfinite(self.minimum_similarity):
            raise ValueError("Minimum similarity must be finite.")
        if not -1.0 <= self.minimum_similarity <= 1.0:
            raise ValueError("Minimum similarity must be between -1 and 1.")
        if self.candidate_limit < 1:
            raise ValueError("Search candidate limit must be at least 1.")


@dataclass(frozen=True)
class _SemanticMatch:
    chunk: KnowledgeChunk
    similarity: float


@dataclass(frozen=True)
class HybridSearchResult:
    """Expose one sourced result and its reproducible ranking components."""

    chunk: KnowledgeChunk
    score: float
    lexical_score: float
    semantic_similarity: float | None


class HybridKnowledgeSearch:
    """Merge existing lexical results with locally embedded document matches."""

    def __init__(
        self,
        library: SQLiteKnowledgeLibrary,
        store: SQLiteEmbeddingStore,
        provider: EmbeddingProvider,
        config: HybridSearchConfig | None = None,
    ):
        self.library = library
        self.store = store
        self.provider = provider
        self.config = config or HybridSearchConfig()

    def search(self, query: str, limit: int = 5) -> tuple[KnowledgeChunk, ...]:
        """Return hybrid results or lexical results if semantics are unavailable."""
        return tuple(
            result.chunk for result in self.search_with_scores(query, limit)
        )

    def search_with_scores(
        self,
        query: str,
        limit: int = 5,
    ) -> tuple[HybridSearchResult, ...]:
        """Return ranked chunks with combined and component scores."""
        normalized_query = query.strip()
        if not normalized_query:
            return ()
        if limit < 1:
            raise ValueError("Knowledge limit must be at least 1.")
        if not self.library.list_documents(limit=1):
            return ()
        lexical = self.library.search(normalized_query, self.config.candidate_limit)
        try:
            semantic = self._semantic_matches(normalized_query)
        except (EmbeddingError, ValueError):
            return self._lexical_only(lexical)[:limit]
        ranked = self._merge_matches(lexical, semantic)
        return ranked[:limit]

    def _semantic_matches(self, query: str) -> tuple[_SemanticMatch, ...]:
        model = self.provider.ensure_model_available()
        query_vector = self.provider.embed(EmbeddingText(query)).vector
        matches = []
        for embedded in self.store.list_current_chunks(model):
            similarity = cosine_similarity(query_vector, embedded.vector)
            if similarity >= self.config.minimum_similarity:
                matches.append(_SemanticMatch(embedded.chunk, similarity))
        return tuple(matches)

    def _merge_matches(
        self,
        lexical: tuple[KnowledgeChunk, ...],
        semantic: tuple[_SemanticMatch, ...],
    ) -> tuple[HybridSearchResult, ...]:
        lexical_scores = self._lexical_scores(lexical)
        semantic_scores = {match.chunk.id: match for match in semantic}
        chunks = {chunk.id: chunk for chunk in lexical}
        chunks.update({match.chunk.id: match.chunk for match in semantic})
        ranked = tuple(
            self._rank_chunk(chunk, lexical_scores, semantic_scores)
            for chunk in chunks.values()
        )
        return tuple(sorted(ranked, key=self._sort_key))

    def _lexical_only(
        self,
        chunks: tuple[KnowledgeChunk, ...],
    ) -> tuple[HybridSearchResult, ...]:
        scores = self._lexical_scores(chunks)
        return tuple(
            HybridSearchResult(chunk, scores[chunk.id], scores[chunk.id], None)
            for chunk in chunks
        )

    @staticmethod
    def _lexical_scores(chunks: tuple[KnowledgeChunk, ...]) -> dict[int, float]:
        count = len(chunks)
        if count == 0:
            return {}
        return {
            chunk.id: (count - index) / count
            for index, chunk in enumerate(chunks)
        }

    def _rank_chunk(
        self,
        chunk: KnowledgeChunk,
        lexical_scores: dict[int, float],
        semantic_matches: dict[int, _SemanticMatch],
    ) -> HybridSearchResult:
        lexical = lexical_scores.get(chunk.id, 0.0)
        semantic = semantic_matches.get(chunk.id)
        similarity = semantic.similarity if semantic is not None else 0.0
        weight_sum = self.config.lexical_weight + self.config.semantic_weight
        score = (
            self.config.lexical_weight * lexical
            + self.config.semantic_weight * similarity
        ) / weight_sum
        semantic_value = similarity if semantic is not None else None
        return HybridSearchResult(chunk, score, lexical, semantic_value)

    @staticmethod
    def _sort_key(
        match: HybridSearchResult,
    ) -> tuple[float, float, float, str, int, int]:
        return (
            -match.score,
            -(match.semantic_similarity or 0.0),
            -match.lexical_score,
            match.chunk.source_path.casefold(),
            match.chunk.chunk_index,
            match.chunk.id,
        )
