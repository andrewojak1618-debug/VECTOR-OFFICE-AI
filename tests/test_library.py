import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from memory.library import SQLiteKnowledgeLibrary


class SQLiteKnowledgeLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_directory.name)
        self.library = SQLiteKnowledgeLibrary(
            self.root / "memory.db",
            chunk_size=100,
        )

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_imports_and_finds_utf8_document(self):
        document_path = self.root / "projektwissen.md"
        document_path.write_text(
            "# Vector Office AI\n\n"
            "Die deutsche Sprachausgabe verwendet Microsoft Stefan.",
            encoding="utf-8",
        )

        result = self.library.import_document(document_path)
        matches = self.library.search("Welche deutsche Sprachausgabe wird verwendet?")

        self.assertTrue(result.changed)
        self.assertEqual(1, len(self.library.list_documents()))
        self.assertEqual(1, len(matches))
        self.assertEqual("projektwissen", matches[0].title)
        self.assertIn("Microsoft Stefan", matches[0].content)

    def test_unchanged_document_is_not_imported_twice(self):
        document_path = self.root / "wissen.txt"
        document_path.write_text("Vector spricht Deutsch.", encoding="utf-8")

        first = self.library.import_document(document_path)
        second = self.library.import_document(document_path)

        self.assertTrue(first.changed)
        self.assertFalse(second.changed)
        self.assertEqual(first.document.id, second.document.id)
        self.assertEqual(1, len(self.library.list_documents()))

    def test_changed_document_replaces_old_chunks(self):
        document_path = self.root / "wissen.txt"
        document_path.write_text("Vector verwendet die alte Stimme.", encoding="utf-8")
        first = self.library.import_document(document_path)

        document_path.write_text(
            "Vector verwendet jetzt die neue deutsche Stimme.",
            encoding="utf-8",
        )
        second = self.library.import_document(document_path)

        self.assertTrue(second.changed)
        self.assertEqual(first.document.id, second.document.id)
        matches = self.library.search("neue Stimme")
        self.assertEqual(1, len(matches))
        self.assertNotIn("alte Stimme", matches[0].content)
        self.assertIn("neue deutsche Stimme", matches[0].content)

    def test_changed_documents_keep_ordered_metadata_versions(self):
        document_path = self.root / "versioned.txt"
        document_path.write_text("Version eins", encoding="utf-8")
        document = self.library.import_document(document_path).document

        document_path.write_text("Version zwei", encoding="utf-8")
        self.library.import_document(document_path)
        self.library.import_document(document_path)
        versions = self.library.list_document_versions(document.id)

        self.assertEqual([2, 1], [item.version_number for item in versions])
        self.assertNotEqual(versions[0].content_hash, versions[1].content_hash)
        self.assertEqual([1, 1], [item.chunk_count for item in versions])

    def test_existing_database_backfills_current_version_without_data_loss(self):
        database_path = self.root / "legacy.db"
        with closing(sqlite3.connect(database_path)) as connection:
            connection.executescript(
                """
                CREATE TABLE knowledge_documents (
                    id INTEGER PRIMARY KEY,
                    source_path TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    imported_at TEXT NOT NULL
                );
                CREATE TABLE knowledge_chunks (
                    id INTEGER PRIMARY KEY,
                    document_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES knowledge_documents(id)
                        ON DELETE CASCADE,
                    UNIQUE(document_id, chunk_index)
                );
                INSERT INTO knowledge_documents VALUES (
                    7, 'legacy.md', 'legacy', 'abc123', '2026-08-01 10:00:00'
                );
                INSERT INTO knowledge_chunks VALUES (9, 7, 1, 'Bestehender Inhalt');
                """
            )
            connection.commit()

        migrated = SQLiteKnowledgeLibrary(database_path)
        versions = migrated.list_document_versions(7)

        self.assertEqual(1, len(versions))
        self.assertEqual("abc123", versions[0].content_hash)
        self.assertEqual(1, versions[0].chunk_count)

    def test_changed_document_preserves_only_identical_chunk_ids(self):
        document_path = self.root / "abschnitte.txt"
        first_text = "A" * 90
        document_path.write_text(f"{first_text}\n\n{'B' * 90}", encoding="utf-8")
        document = self.library.import_document(document_path).document
        original = self.library.list_chunks(document.id)

        document_path.write_text(f"{first_text}\n\n{'C' * 90}", encoding="utf-8")
        self.library.import_document(document_path)
        updated = self.library.list_chunks(document.id)

        self.assertEqual(original[0].id, updated[0].id)
        self.assertNotEqual(original[1].id, updated[1].id)

    def test_removed_sections_are_deleted(self):
        document_path = self.root / "kurzer.txt"
        first_text = "A" * 90
        document_path.write_text(f"{first_text}\n\n{'B' * 90}", encoding="utf-8")
        document = self.library.import_document(document_path).document
        self.assertEqual(2, len(self.library.list_chunks(document.id)))

        document_path.write_text(first_text, encoding="utf-8")
        self.library.import_document(document_path)

        self.assertEqual(1, len(self.library.list_chunks(document.id)))

    def test_rejects_unsupported_file_type(self):
        document_path = self.root / "secret.json"
        document_path.write_text('{"key": "value"}', encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "document types"):
            self.library.import_document(document_path)

    def test_rejects_file_over_size_limit(self):
        library = SQLiteKnowledgeLibrary(
            self.root / "small.db",
            max_file_bytes=10,
        )
        document_path = self.root / "large.txt"
        document_path.write_text("12345678901", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "exceeds"):
            library.import_document(document_path)

    def test_forget_document_removes_document_and_chunks(self):
        document_path = self.root / "wissen.txt"
        document_path.write_text("Vector kennt dieses Projektwissen.", encoding="utf-8")
        imported = self.library.import_document(document_path)

        self.assertTrue(self.library.forget_document(imported.document.id))
        self.assertFalse(self.library.forget_document(imported.document.id))
        self.assertEqual((), self.library.list_documents())
        self.assertEqual((), self.library.list_document_versions(imported.document.id))
        self.assertEqual((), self.library.search("Projektwissen"))


if __name__ == "__main__":
    unittest.main()
