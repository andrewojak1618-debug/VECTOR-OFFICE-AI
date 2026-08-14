import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from memory.embedding_store import ChunkEmbedding, SQLiteEmbeddingStore
from memory.embeddings import (
    EmbeddingError,
    EmbeddingModelInfo,
    EmbeddingResult,
    EmbeddingText,
    EmbeddingVector,
)
from memory.library import SQLiteKnowledgeLibrary
from memory.search import (
    HybridKnowledgeSearch,
    HybridSearchConfig,
    cosine_similarity,
)


class FixedQueryProvider:
    def __init__(self, query_vector=(1.0, 0.0), unavailable=False):
        self.model = EmbeddingModelInfo("embeddinggemma", "version-one", 2)
        self.query_vector = EmbeddingVector(query_vector)
        self.unavailable = unavailable
        self.embedded_queries = []

    @property
    def model_name(self):
        return self.model.model_name

    @property
    def model_version(self):
        return self.model.model_version

    @property
    def dimension(self):
        return self.model.dimension

    def ensure_model_available(self):
        if self.unavailable:
            raise EmbeddingError("local service unavailable")
        return self.model

    def embed(self, text):
        self.embedded_queries.append(text.value)
        return EmbeddingResult(text, self.query_vector, self.model.model_name)

    def embed_many(self, texts):
        return tuple(self.embed(text) for text in texts)


class CosineSimilarityTests(unittest.TestCase):
    def test_identical_and_orthogonal_vectors(self):
        base = EmbeddingVector((1.0, 0.0))

        self.assertAlmostEqual(1.0, cosine_similarity(base, base))
        self.assertAlmostEqual(
            0.0,
            cosine_similarity(base, EmbeddingVector((0.0, 1.0))),
        )

    def test_zero_vector_is_safe_and_dimension_mismatch_is_rejected(self):
        self.assertEqual(
            0.0,
            cosine_similarity(
                EmbeddingVector((0.0, 0.0)),
                EmbeddingVector((1.0, 0.0)),
            ),
        )
        with self.assertRaisesRegex(ValueError, "dimensions"):
            cosine_similarity(
                EmbeddingVector((1.0,)),
                EmbeddingVector((1.0, 0.0)),
            )


class HybridSearchConfigTests(unittest.TestCase):
    def test_non_finite_ranking_values_are_rejected(self):
        for name, value in (
            ("lexical_weight", float("nan")),
            ("semantic_weight", float("inf")),
            ("minimum_similarity", float("nan")),
        ):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "finite"):
                    HybridSearchConfig(**{name: value})


class HybridKnowledgeSearchTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_directory.name)
        database_path = self.root / "memory.db"
        self.library = SQLiteKnowledgeLibrary(database_path, chunk_size=100)
        self.store = SQLiteEmbeddingStore(database_path)
        self.provider = FixedQueryProvider()

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_semantic_weight_can_rank_meaning_above_lexical_match(self):
        lexical = self._add_document("lexical.txt", "Suchwort im Text", (0.0, 1.0))
        semantic = self._add_document("semantic.txt", "Verwandte Bedeutung", (1.0, 0.0))
        search = self._search(
            lexical_weight=0.2,
            semantic_weight=0.8,
            minimum_similarity=0.0,
        )

        results = search.search("Suchwort", limit=2)

        self.assertEqual([semantic.id, lexical.id], [chunk.id for chunk in results])
        self.assertEqual(["Suchwort"], self.provider.embedded_queries)

    def test_minimum_similarity_excludes_weak_semantic_only_match(self):
        self._add_document("weak.txt", "Inhalt ohne Abfragewort", (0.7, 0.714))
        search = self._search(minimum_similarity=0.8)

        self.assertEqual((), search.search("Suchwort"))

    def test_duplicate_lexical_and_semantic_match_is_returned_once(self):
        chunk = self._add_document("same.txt", "Suchwort und Bedeutung", (1.0, 0.0))

        results = self._search(minimum_similarity=0.0).search("Suchwort")

        self.assertEqual((chunk.id,), tuple(result.id for result in results))
        self.assertEqual(chunk.source_path, results[0].source_path)
        self.assertEqual(chunk.chunk_index, results[0].chunk_index)

    def test_limit_and_source_order_make_equal_scores_deterministic(self):
        first = self._add_document("a.txt", "Erster Inhalt", (1.0, 0.0))
        second = self._add_document("b.txt", "Zweiter Inhalt", (1.0, 0.0))
        self._add_document("c.txt", "Dritter Inhalt", (1.0, 0.0))

        results = self._search(minimum_similarity=0.0).search("Suchwort", limit=2)

        self.assertEqual([first.id, second.id], [chunk.id for chunk in results])

    def test_unavailable_embedding_service_falls_back_to_lexical_search(self):
        expected = self._add_document(
            "memory.txt",
            "Das Lieblingsprojekt heißt Vector Office AI.",
            (1.0, 0.0),
        )
        self.provider.unavailable = True

        results = self._search().search("Lieblingsprojekt")

        self.assertEqual((expected.id,), tuple(chunk.id for chunk in results))
        self.assertEqual([], self.provider.embedded_queries)

    def test_scored_results_expose_source_and_similarity(self):
        expected = self._add_document(
            "scored.txt",
            "Semantisch passender Abschnitt",
            (1.0, 0.0),
        )

        result = self._search(minimum_similarity=0.0).search_with_scores(
            "Suchwort",
            limit=1,
        )[0]

        self.assertEqual(expected.source_path, result.chunk.source_path)
        self.assertEqual(expected.chunk_index, result.chunk.chunk_index)
        self.assertAlmostEqual(1.0, result.semantic_similarity)
        self.assertGreater(result.score, 0.0)

    def test_other_model_version_is_not_used_for_semantic_search(self):
        chunk = self._add_document("old.txt", "Nur alter Modellvektor", (1.0, 0.0))
        self.provider.model = EmbeddingModelInfo("embeddinggemma", "version-two", 2)

        results = self._search(minimum_similarity=0.0).search("Suchwort")

        self.assertEqual((), results)
        self.assertNotEqual("Suchwort", chunk.content)

    def test_search_does_not_log_query_document_or_vector_values(self):
        secret = "Vertraulicher Dokumentinhalt 4711"
        self._add_document("private.txt", secret, (1.0, 0.0))

        with patch("sys.stdout", new_callable=io.StringIO) as output:
            self._search(minimum_similarity=0.0).search("Vertrauliche Frage")

        self.assertEqual("", output.getvalue())
        self.assertNotIn(secret, output.getvalue())

    def _search(self, **overrides):
        values = {
            "lexical_weight": 0.45,
            "semantic_weight": 0.55,
            "minimum_similarity": 0.35,
        }
        values.update(overrides)
        return HybridKnowledgeSearch(
            self.library,
            self.store,
            self.provider,
            HybridSearchConfig(**values),
        )

    def _add_document(self, name: str, content: str, vector: tuple[float, ...]):
        path = self.root / name
        path.write_text(content, encoding="utf-8")
        document = self.library.import_document(path).document
        chunk = self.library.list_chunks(document.id)[0]
        result = EmbeddingResult(
            EmbeddingText(chunk.content),
            EmbeddingVector(vector),
            "embeddinggemma",
        )
        self.store.save(ChunkEmbedding(chunk.id, result), self.provider.model)
        return chunk


if __name__ == "__main__":
    unittest.main()
