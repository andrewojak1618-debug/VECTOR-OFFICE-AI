import tempfile
import unittest
from pathlib import Path

from memory.embedding_store import ChunkEmbedding, SQLiteEmbeddingStore
from memory.embeddings import (
    EmbeddingError,
    EmbeddingModelInfo,
    EmbeddingResult,
    EmbeddingText,
    EmbeddingVector,
)
from memory.library import SQLiteKnowledgeLibrary
from memory.search import HybridKnowledgeSearch, HybridSearchConfig


TARGET_FACT = (
    "Die Notabschaltung des Serverraums befindet sich hinter der blauen "
    "Abdeckung direkt neben der Eingangstür."
)
SIMILAR_FACT = (
    "Der Hauptschalter der Werkstatt befindet sich im grauen Schaltschrank "
    "neben dem Fenster."
)
DISTRACTOR_FACT = (
    "Die monatliche Datensicherung wird jeweils am ersten Freitag geprüft."
)
DIRECT_QUERY = "Wo befindet sich die Notabschaltung des Serverraums?"
PARAPHRASE_QUERY = (
    "Wo trennt man bei Gefahr die Rechneranlage vollständig vom elektrischen Netz?"
)
NOISY_QUERY = (
    "Wetterbericht und Kaffeepause sind heute nebensächlich. "
    "Wo trennt man bei Gefahr die Rechneranlage vollständig vom elektrischen Netz?"
)
UNRELATED_QUERY = "Welche Temperatur benötigt ein Apfelkuchen?"


class ParaphraseEmbeddingProvider:
    def __init__(self, unavailable: bool = False):
        self.model = EmbeddingModelInfo("embeddinggemma", "test-version", 3)
        self.unavailable = unavailable
        self.query_vectors = {
            DIRECT_QUERY: (1.0, 0.0, 0.0),
            PARAPHRASE_QUERY: (1.0, 0.0, 0.0),
            NOISY_QUERY: (1.0, 0.0, 0.0),
            UNRELATED_QUERY: (0.0, 0.0, 1.0),
            "Wo liegt der Hauptschalter?": (1.0, 0.0, 0.0),
        }

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
            raise EmbeddingError("local Ollama unavailable")
        return self.model

    def embed(self, text):
        vector = self.query_vectors.get(text.value, (0.0, 0.0, 1.0))
        return EmbeddingResult(
            text,
            EmbeddingVector(vector),
            self.model.model_name,
        )

    def embed_many(self, texts):
        return tuple(self.embed(text) for text in texts)


class SemanticParaphraseTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_directory.name)
        database_path = self.root / "memory.db"
        self.library = SQLiteKnowledgeLibrary(database_path, chunk_size=120)
        self.store = SQLiteEmbeddingStore(database_path)
        self.provider = ParaphraseEmbeddingProvider()
        self.chunks = self._import_test_document()

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_direct_question_finds_unique_fact(self):
        result = self._search().search(DIRECT_QUERY, limit=1)

        self.assertEqual(self.chunks[0].id, result[0].id)

    def test_paraphrase_without_shared_terms_finds_unique_fact(self):
        self.assertEqual((), self.library.search(PARAPHRASE_QUERY))

        result = self._search().search(PARAPHRASE_QUERY, limit=1)

        self.assertEqual(self.chunks[0].id, result[0].id)

    def test_irrelevant_additions_do_not_change_top_result(self):
        result = self._search().search(NOISY_QUERY, limit=1)

        self.assertEqual(self.chunks[0].id, result[0].id)

    def test_similar_sections_are_ranked_by_semantic_closeness(self):
        result = self._search().search(PARAPHRASE_QUERY, limit=2)

        self.assertEqual(
            [self.chunks[0].id, self.chunks[1].id],
            [chunk.id for chunk in result],
        )

    def test_minimum_similarity_excludes_weaker_similar_section(self):
        result = self._search(minimum_similarity=0.9).search(
            PARAPHRASE_QUERY,
            limit=3,
        )

        self.assertEqual((self.chunks[0].id,), tuple(chunk.id for chunk in result))

    def test_unrelated_question_produces_no_false_positive(self):
        result = self._search(minimum_similarity=0.5).search(UNRELATED_QUERY)

        self.assertEqual((), result, "False positives must remain documented as zero.")

    def test_semantic_weight_can_correct_lexical_ranking(self):
        result = self._search(
            lexical_weight=0.1,
            semantic_weight=0.9,
        ).search("Wo liegt der Hauptschalter?", limit=2)

        self.assertEqual(self.chunks[0].id, result[0].id)
        self.assertEqual(self.chunks[1].id, result[1].id)

    def test_empty_library_returns_no_results(self):
        empty_path = self.root / "empty.db"
        library = SQLiteKnowledgeLibrary(empty_path, chunk_size=120)
        search = HybridKnowledgeSearch(
            library,
            SQLiteEmbeddingStore(empty_path),
            self.provider,
        )

        self.assertEqual((), search.search(PARAPHRASE_QUERY))

    def test_unreachable_ollama_falls_back_to_direct_lexical_match(self):
        search = HybridKnowledgeSearch(
            self.library,
            self.store,
            ParaphraseEmbeddingProvider(unavailable=True),
        )

        result = search.search(DIRECT_QUERY, limit=1)

        self.assertEqual(self.chunks[0].id, result[0].id)

    def _search(self, **overrides):
        values = {
            "lexical_weight": 0.45,
            "semantic_weight": 0.55,
            "minimum_similarity": 0.5,
        }
        values.update(overrides)
        return HybridKnowledgeSearch(
            self.library,
            self.store,
            self.provider,
            HybridSearchConfig(**values),
        )

    def _import_test_document(self):
        path = self.root / "eindeutige-fakten.md"
        path.write_text(
            "\n\n".join((TARGET_FACT, SIMILAR_FACT, DISTRACTOR_FACT)),
            encoding="utf-8",
        )
        document = self.library.import_document(path).document
        chunks = self.library.list_chunks(document.id)
        vectors = ((1.0, 0.0, 0.0), (0.75, 0.661, 0.0), (0.0, 1.0, 0.0))
        self.store.save_many(
            tuple(
                self._embedding(chunk, vector)
                for chunk, vector in zip(chunks, vectors)
            ),
            self.provider.model,
        )
        return chunks

    @staticmethod
    def _embedding(chunk, vector):
        return ChunkEmbedding(
            chunk.id,
            EmbeddingResult(
                EmbeddingText(chunk.content),
                EmbeddingVector(vector),
                "embeddinggemma",
            ),
        )


if __name__ == "__main__":
    unittest.main()
