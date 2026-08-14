import tempfile
import unittest
from pathlib import Path

from memory.database import SQLiteMemoryStore


class SQLiteMemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_directory.name) / "memory.db"
        self.store = SQLiteMemoryStore(database_path)

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_remember_and_list_memories(self):
        saved = self.store.remember("Andres Lieblingsprojekt heißt Vector Office AI.")

        memories = self.store.list_memories()

        self.assertEqual(saved.id, memories[0].id)
        self.assertEqual("user-confirmed", memories[0].source)

    def test_remember_updates_duplicate_without_creating_second_entry(self):
        first = self.store.remember("Vector spricht Deutsch.")
        second = self.store.remember("vector spricht deutsch.")

        self.assertEqual(first.id, second.id)
        self.assertEqual(1, len(self.store.list_memories()))

    def test_search_returns_matching_memory(self):
        self.store.remember("Andres Lieblingsprojekt heißt Vector Office AI.")
        self.store.remember("Vector verwendet eine deutsche Stimme.")

        results = self.store.search("Wie heißt mein Lieblingsprojekt?")

        self.assertEqual(1, len(results))
        self.assertIn("Lieblingsprojekt", results[0].content)

    def test_confirmed_feedback_is_listed_separately(self):
        self.store.remember("Vector spricht Deutsch.")
        saved = self.store.remember(
            "Bitte antworte weniger belehrend.",
            category="feedback",
            source="user-confirmed-feedback",
        )

        feedback = self.store.list_feedback()

        self.assertEqual((saved,), feedback)
        self.assertEqual("feedback", feedback[0].category)
        self.assertEqual("user-confirmed-feedback", feedback[0].source)

    def test_style_feedback_is_not_returned_as_factual_memory(self):
        self.store.remember(
            "Antworte bei Projektfragen immer sehr kurz.",
            category="feedback",
            source="user-confirmed-feedback",
        )

        results = self.store.search("Wie sollst du bei Projektfragen antworten?")

        self.assertEqual((), results)

    def test_forget_deletes_memory(self):
        saved = self.store.remember("Diese Erinnerung wird gelöscht.")

        self.assertTrue(self.store.forget(saved.id))
        self.assertFalse(self.store.forget(saved.id))
        self.assertEqual((), self.store.list_memories())


if __name__ == "__main__":
    unittest.main()
