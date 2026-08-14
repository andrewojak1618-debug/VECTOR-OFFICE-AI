import tempfile
import unittest
from pathlib import Path

from memory.embedding_store import SQLiteEmbeddingStore
from memory.embeddings import (
    EmbeddingError,
    EmbeddingModelInfo,
    EmbeddingResult,
    EmbeddingVector,
)
from memory.indexing import (
    DocumentEmbeddingIndexer,
    IndexedKnowledgeLibrary,
)
from memory.library import SQLiteKnowledgeLibrary


class TrackingEmbeddingProvider:
    def __init__(
        self,
        model_version: str = "version-one",
        fail_on_call: int | None = None,
    ):
        self.model = EmbeddingModelInfo("embeddinggemma", model_version, 3)
        self.fail_on_call = fail_on_call
        self.calls = 0
        self.embedded_texts: list[str] = []
        self.unavailable = False

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
        return self.embed_many((text,))[0]

    def embed_many(self, texts):
        self.calls += 1
        if self.calls == self.fail_on_call:
            raise RuntimeError("simulated local embedding failure")
        self.embedded_texts.extend(text.value for text in texts)
        return tuple(
            EmbeddingResult(
                text,
                EmbeddingVector((0.1, 0.2, 0.3)),
                self.model.model_name,
            )
            for text in texts
        )


class AutomaticIndexingTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_directory.name)
        self.database_path = self.root / "memory.db"
        self.raw_library = SQLiteKnowledgeLibrary(
            self.database_path,
            chunk_size=100,
        )
        self.store = SQLiteEmbeddingStore(self.database_path)
        self.provider = TrackingEmbeddingProvider()
        self.indexer = DocumentEmbeddingIndexer(
            self.raw_library,
            self.store,
            self.provider,
        )
        self.library = IndexedKnowledgeLibrary(self.raw_library, self.indexer)

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_import_automatically_indexes_all_new_sections(self):
        path = self._write_sections("A", "B")

        imported = self.library.import_document(str(path))
        indexing = self.library.last_indexing_result

        self.assertTrue(imported.changed)
        self.assertEqual(2, indexing.indexed_chunks)
        self.assertEqual(2, len(self.store.list_for_document(imported.document.id)))

    def test_unchanged_sha256_document_skips_embedding_calculation(self):
        path = self._write_sections("A", "B")
        first = self.library.import_document(str(path))
        calls_after_first_import = self.provider.calls

        second = self.library.import_document(str(path))

        self.assertFalse(second.changed)
        self.assertEqual(calls_after_first_import, self.provider.calls)
        self.assertEqual(0, self.library.last_indexing_result.indexed_chunks)
        self.assertEqual(first.document.id, second.document.id)

    def test_only_changed_section_is_reindexed(self):
        path = self._write_sections("A", "B")
        imported = self.library.import_document(str(path))
        original_chunks = self.raw_library.list_chunks(imported.document.id)
        self.provider.embedded_texts.clear()

        self._write_sections("A", "C")
        self.library.import_document(str(path))
        current_chunks = self.raw_library.list_chunks(imported.document.id)

        self.assertEqual(1, self.library.last_indexing_result.indexed_chunks)
        self.assertEqual(["C" * 90], self.provider.embedded_texts)
        self.assertEqual(original_chunks[0].id, current_chunks[0].id)
        self.assertNotEqual(original_chunks[1].id, current_chunks[1].id)

    def test_removed_sections_and_vectors_are_deleted(self):
        path = self._write_sections("A", "B")
        imported = self.library.import_document(str(path))

        path.write_text("A" * 90, encoding="utf-8")
        self.library.import_document(str(path))

        self.assertEqual(1, len(self.raw_library.list_chunks(imported.document.id)))
        self.assertEqual(1, len(self.store.list_for_document(imported.document.id)))
        self.assertEqual(0, self.library.last_indexing_result.indexed_chunks)

    def test_model_switch_is_detected_and_indexes_every_section(self):
        path = self._write_sections("A", "B")
        imported = self.library.import_document(str(path))
        new_provider = TrackingEmbeddingProvider("version-two")
        switched = DocumentEmbeddingIndexer(
            self.raw_library,
            self.store,
            new_provider,
        )

        result = switched.index_document(imported.document.id)

        self.assertTrue(result.model_changed)
        self.assertEqual(2, result.indexed_chunks)
        self.assertEqual((), self.store.pending_chunk_ids(
            imported.document.id,
            new_provider.model,
        ))

    def test_manual_reindex_forces_current_sections(self):
        path = self._write_sections("A", "B")
        imported = self.library.import_document(str(path))
        calls_before = self.provider.calls

        result = self.library.reindex_document(imported.document.id)

        self.assertTrue(result.forced)
        self.assertEqual(2, result.indexed_chunks)
        self.assertEqual(calls_before + 1, self.provider.calls)

    def test_full_reindex_rebuilds_every_imported_document(self):
        first_path = self._write_document("first.md", "A")
        second_path = self._write_document("second.md", "B")
        self.library.import_document(str(first_path))
        self.library.import_document(str(second_path))

        results = self.library.reindex_all()

        self.assertEqual(2, len(results))
        self.assertTrue(all(result.forced for result in results))
        self.assertEqual(results, self.library.last_reindex_results)

    def test_status_exposes_model_versions_and_stale_vector_counts(self):
        imported = self.library.import_document(str(self._write_sections("A", "B")))
        new_provider = TrackingEmbeddingProvider("version-two")
        switched = IndexedKnowledgeLibrary(
            self.raw_library,
            DocumentEmbeddingIndexer(self.raw_library, self.store, new_provider),
        )

        status = switched.list_document_statuses()[0]
        stale = switched.list_stale_vectors()

        self.assertEqual(imported.document.id, status.document.id)
        self.assertEqual("version-two", status.model_version)
        self.assertEqual(0, status.current_vectors)
        self.assertEqual(2, status.stale_vectors)
        self.assertEqual(2, len(stale))

    def test_document_overview_uses_stored_model_when_ollama_is_offline(self):
        imported = self.library.import_document(str(self._write_sections("A")))
        self.provider.unavailable = True

        status = self.library.list_document_statuses()[0]

        self.assertEqual(imported.document.id, status.document.id)
        self.assertEqual("embeddinggemma", status.model_name)
        self.assertEqual("version-one", status.model_version)
        self.assertEqual(1, status.current_vectors)

    def test_verified_deletion_removes_document_versions_and_vectors(self):
        imported = self.library.import_document(str(self._write_sections("A", "B")))

        self.assertTrue(self.library.forget_document(imported.document.id))

        self.assertFalse(self.raw_library.document_exists(imported.document.id))
        self.assertEqual((), self.raw_library.list_document_versions(imported.document.id))
        self.assertEqual((), self.store.list_for_document(imported.document.id))

    def test_failure_before_persistence_leaves_no_partial_index(self):
        path = self._write_sections("A", "B", "C")
        imported = self.raw_library.import_document(str(path))
        failing_provider = TrackingEmbeddingProvider(fail_on_call=2)
        indexer = DocumentEmbeddingIndexer(
            self.raw_library,
            self.store,
            failing_provider,
            batch_size=1,
        )

        with self.assertRaisesRegex(RuntimeError, "simulated"):
            indexer.index_document(imported.document.id)

        self.assertEqual((), self.store.list_for_document(imported.document.id))

    def test_large_document_reports_batch_progress(self):
        path = self._write_sections("A", "B", "C", "D", "E")
        imported = self.raw_library.import_document(str(path))
        progress = []
        indexer = DocumentEmbeddingIndexer(
            self.raw_library,
            self.store,
            self.provider,
            batch_size=2,
        )

        indexer.index_document(
            imported.document.id,
            progress=lambda state: progress.append((state.completed, state.total)),
        )

        self.assertEqual([(2, 5), (4, 5), (5, 5)], progress)

    def _write_sections(self, *markers: str) -> Path:
        path = self.root / "wissen.md"
        path.write_text(
            "\n\n".join(marker * 90 for marker in markers),
            encoding="utf-8",
        )
        return path

    def _write_document(self, name: str, marker: str) -> Path:
        path = self.root / name
        path.write_text(marker * 90, encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
