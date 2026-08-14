import tempfile
import unittest
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
        self.assertEqual((), self.library.search("Projektwissen"))


if __name__ == "__main__":
    unittest.main()
