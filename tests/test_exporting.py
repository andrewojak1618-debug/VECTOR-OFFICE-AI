"""Regression tests for separate, secret-aware local JSON exports."""

import json
import tempfile
import unittest
from pathlib import Path

from memory.database import SQLiteMemoryStore
from memory.embedding_store import SQLiteEmbeddingStore
from memory.indexing import DocumentEmbeddingIndexer, IndexedKnowledgeLibrary
from memory.library import SQLiteKnowledgeLibrary
from tests.test_indexing import TrackingEmbeddingProvider


class LocalExportTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_directory.name)
        self.database_path = self.root / "memory.db"
        self.raw_library = SQLiteKnowledgeLibrary(self.database_path)
        self.store = SQLiteEmbeddingStore(self.database_path)
        self.provider = TrackingEmbeddingProvider()
        self.library = IndexedKnowledgeLibrary(
            self.raw_library,
            DocumentEmbeddingIndexer(
                self.raw_library,
                self.store,
                self.provider,
            ),
        )
        self.memories = SQLiteMemoryStore(self.database_path)

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_library_export_contains_metadata_without_content_or_vectors(self):
        source = self.root / "project-fact.md"
        source.write_text("Private document content 4711", encoding="utf-8")
        imported = self.library.import_document(str(source))

        destination = self.library.export_library_metadata(
            self.root / "library-export.json"
        )
        payload = json.loads(destination.read_text(encoding="utf-8"))
        encoded = destination.read_text(encoding="utf-8")

        self.assertEqual("vector-office-ai-library-metadata", payload["export_type"])
        self.assertEqual(imported.document.content_hash, payload["documents"][0]["content_hash"])
        self.assertEqual("embeddinggemma", payload["documents"][0]["embedding"]["model_name"])
        self.assertNotIn("Private document content", encoded)
        self.assertNotIn(str(self.root), encoded)
        self.assertNotIn("vector", payload["documents"][0]["embedding"])

    def test_memory_export_is_separate_and_redacts_common_secrets(self):
        secret = "OPENAI_API_KEY=sk-testSecret123456789"
        self.memories.remember(f"Temporärer Schlüssel: {secret}")

        destination = self.memories.export_confirmed_memories(
            self.root / "memory-export.json"
        )
        encoded = destination.read_text(encoding="utf-8")
        payload = json.loads(encoded)

        self.assertEqual("vector-office-ai-confirmed-memories", payload["export_type"])
        self.assertIn("[REDACTED]", encoded)
        self.assertNotIn("sk-testSecret", encoded)
        self.assertNotIn("documents", payload)

    def test_export_rejects_non_json_destination(self):
        with self.assertRaisesRegex(ValueError, "JSON"):
            self.memories.export_confirmed_memories(self.root / "unsafe.txt")


if __name__ == "__main__":
    unittest.main()
