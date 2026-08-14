import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from memory.embedding_store import (
    ChunkEmbedding,
    Float32VectorCodec,
    SQLiteEmbeddingStore,
)
from memory.embeddings import (
    EmbeddingModelInfo,
    EmbeddingResult,
    EmbeddingText,
    EmbeddingVector,
)
from memory.indexing import DocumentEmbeddingIndexer
from memory.library import SQLiteKnowledgeLibrary


class FakeEmbeddingProvider:
    def __init__(self, model: EmbeddingModelInfo):
        self.model = model
        self.batch_calls = 0

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
        return self.model

    def embed(self, text):
        return self.embed_many((text,))[0]

    def embed_many(self, texts):
        self.batch_calls += 1
        return tuple(
            EmbeddingResult(
                text,
                EmbeddingVector((index + 0.1, index + 0.2, index + 0.3)),
                self.model.model_name,
            )
            for index, text in enumerate(texts)
        )


class Float32VectorCodecTests(unittest.TestCase):
    def test_vector_uses_four_bytes_per_dimension(self):
        vector = EmbeddingVector((0.1, 0.2, 0.3))

        payload = Float32VectorCodec.encode(vector)
        restored = Float32VectorCodec.decode(payload, vector.dimension)

        self.assertEqual(12, len(payload))
        for expected, actual in zip(vector.values, restored.values):
            self.assertAlmostEqual(expected, actual, places=6)


class SQLiteEmbeddingStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_directory.name)
        self.database_path = self.root / "memory.db"
        self.library = SQLiteKnowledgeLibrary(self.database_path, chunk_size=100)
        self.store = SQLiteEmbeddingStore(self.database_path)
        self.document = self._import_document()
        self.chunks = self.library.list_chunks(self.document.id)
        self.model = self._model("version-one")

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_stores_chunk_model_version_dimension_and_vector(self):
        stored = self.store.save(self._embedding(self.chunks[0]), self.model)

        self.assertEqual(self.chunks[0].id, stored.chunk_id)
        self.assertEqual("embeddinggemma", stored.model_name)
        self.assertEqual("version-one", stored.model_version)
        self.assertEqual(3, stored.dimension)
        self.assertEqual(3, stored.vector.dimension)
        self.assertEqual(64, len(stored.content_hash))

    def test_duplicate_identity_is_upserted_not_duplicated(self):
        first = self.store.save(self._embedding(self.chunks[0]), self.model)
        second = self.store.save(self._embedding(self.chunks[0]), self.model)

        stored = self.store.list_for_document(self.document.id)
        self.assertEqual(first.id, second.id)
        self.assertEqual(1, len(stored))

    def test_failed_batch_is_rolled_back_atomically(self):
        invalid_result = EmbeddingResult(
            EmbeddingText("Nicht der zweite Abschnitt"),
            EmbeddingVector((0.4, 0.5, 0.6)),
            "embeddinggemma",
        )
        batch = (
            self._embedding(self.chunks[0]),
            ChunkEmbedding(self.chunks[1].id, invalid_result),
        )

        with self.assertRaisesRegex(ValueError, "does not match"):
            self.store.save_many(batch, self.model)

        self.assertEqual((), self.store.list_for_document(self.document.id))

    def test_old_model_version_is_recognized_as_stale(self):
        self.store.save(self._embedding(self.chunks[0]), self.model)

        self.assertEqual(
            (),
            self.store.list_stale_for_document(self.document.id, self.model),
        )
        stale = self.store.list_stale_for_document(
            self.document.id,
            self._model("version-two"),
        )
        self.assertEqual(1, len(stale))
        self.assertEqual("version-one", stale[0].model_version)

    def test_embedding_text_must_match_database_chunk(self):
        mismatched = ChunkEmbedding(
            self.chunks[0].id,
            EmbeddingResult(
                EmbeddingText("Falscher Abschnitt"),
                EmbeddingVector((0.1, 0.2, 0.3)),
                "embeddinggemma",
            ),
        )

        with self.assertRaisesRegex(ValueError, "does not match"):
            self.store.save(mismatched, self.model)

    def test_deleting_document_cascades_through_chunks_and_embeddings(self):
        stored = self.store.save(self._embedding(self.chunks[0]), self.model)

        self.assertTrue(self.library.forget_document(self.document.id))
        self.assertEqual((), self.store.list_for_document(self.document.id))
        with closing(sqlite3.connect(self.database_path)) as connection:
            remaining = connection.execute(
                "SELECT COUNT(*) FROM knowledge_embeddings WHERE id = ?",
                (stored.id,),
            ).fetchone()[0]
        self.assertEqual(0, remaining)

    def test_changed_document_removes_embeddings_for_replaced_chunks(self):
        self.store.save(self._embedding(self.chunks[0]), self.model)
        document_path = Path(self.document.source_path)
        document_path.write_text("Vollständig erneuerter Inhalt.", encoding="utf-8")

        updated = self.library.import_document(document_path)

        self.assertTrue(updated.changed)
        self.assertEqual((), self.store.list_for_document(self.document.id))

    def test_indexer_embeds_all_chunks_in_one_batch_and_persists_them(self):
        provider = FakeEmbeddingProvider(self.model)
        indexer = DocumentEmbeddingIndexer(self.library, self.store, provider)

        result = indexer.index_document(self.document.id)

        self.assertEqual(1, provider.batch_calls)
        self.assertEqual(len(self.chunks), result.indexed_chunks)
        self.assertEqual(len(self.chunks), len(self.store.list_for_document(self.document.id)))

    def _import_document(self):
        document_path = self.root / "wissen.md"
        document_path.write_text(
            "Erster Abschnitt über lokale Erinnerungen und Vector Office AI.\n\n"
            "Zweiter Abschnitt über Dokumentwissen und semantische Vektoren.",
            encoding="utf-8",
        )
        return self.library.import_document(document_path).document

    @staticmethod
    def _model(version: str) -> EmbeddingModelInfo:
        return EmbeddingModelInfo("embeddinggemma", version, 3)

    @staticmethod
    def _embedding(chunk) -> ChunkEmbedding:
        result = EmbeddingResult(
            EmbeddingText(chunk.content),
            EmbeddingVector((0.1, 0.2, 0.3)),
            "embeddinggemma",
        )
        return ChunkEmbedding(chunk.id, result)


class EmbeddingSchemaMigrationTests(unittest.TestCase):
    def test_existing_knowledge_database_is_extended_without_data_loss(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "legacy.db"
            self._create_legacy_database(database_path)

            SQLiteEmbeddingStore(database_path)

            with closing(sqlite3.connect(database_path)) as connection:
                title = connection.execute(
                    "SELECT title FROM knowledge_documents WHERE id = 1"
                ).fetchone()[0]
                table = connection.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type = 'table' AND name = 'knowledge_embeddings'
                    """
                ).fetchone()
            self.assertEqual("Bestandsdokument", title)
            self.assertEqual(("knowledge_embeddings",), table)

    @staticmethod
    def _create_legacy_database(database_path: Path) -> None:
        with closing(sqlite3.connect(database_path)) as connection:
            connection.executescript(
                """
                CREATE TABLE knowledge_documents (
                    id INTEGER PRIMARY KEY,
                    source_path TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE knowledge_chunks (
                    id INTEGER PRIMARY KEY,
                    document_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES knowledge_documents(id)
                        ON DELETE CASCADE
                );
                INSERT INTO knowledge_documents
                    (id, source_path, title, content_hash)
                VALUES (1, 'legacy.txt', 'Bestandsdokument', 'legacy-hash');
                INSERT INTO knowledge_chunks
                    (id, document_id, chunk_index, content)
                VALUES (1, 1, 1, 'Bestehender Inhalt');
                """
            )


if __name__ == "__main__":
    unittest.main()
