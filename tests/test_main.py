import io
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from main import run_conversation, run_voice_conversation


class FakeContext:
    def __init__(self):
        self.clear_count = 0

    def clear(self):
        self.clear_count += 1


class FakeAgent:
    def __init__(self):
        self.context = FakeContext()
        self.memory_store = None
        self.knowledge_library = None
        self.requests = []

    def respond(self, user_text):
        self.requests.append(user_text)
        return f"Antwort auf: {user_text}"


class FakeSpeech:
    def __init__(self):
        self.spoken = []

    def say(self, text):
        self.spoken.append(text)
        return True


class FakeMemoryStore:
    def __init__(self):
        self.saved = []
        self.feedback = []
        self.deleted = []
        self.exported = []

    def remember(self, content, category="fact", source="user-confirmed"):
        self.saved.append(content)
        if category == "feedback":
            self.feedback.append((content, source))
        return SimpleNamespace(id=3, content=content)

    def list_memories(self):
        return (SimpleNamespace(id=3, content=self.saved[-1]),)

    def forget(self, memory_id):
        self.deleted.append(memory_id)
        return True

    def export_confirmed_memories(self, destination):
        self.exported.append(destination)
        return Path(destination)


class FakeKnowledgeLibrary:
    def __init__(self):
        self.imported = []
        self.deleted = []
        self.reindexed = []
        self.exported = []
        self.last_indexing_result = None

    def import_document(self, path):
        self.imported.append(path)
        return SimpleNamespace(
            document=SimpleNamespace(id=4, title="projektwissen"),
            chunk_count=2,
            changed=True,
        )

    def list_document_statuses(self):
        return (
            SimpleNamespace(
                document=SimpleNamespace(
                    id=4,
                    title="projektwissen",
                    source_path="C:\\Wissen\\projektwissen.md",
                    imported_at="2026-08-14 12:00:00",
                    content_hash="a" * 64,
                ),
                version_count=2,
                model_name="embeddinggemma",
                model_version="version-one",
                dimension=768,
                current_vectors=2,
                stale_vectors=0,
            ),
        )

    def forget_document(self, document_id):
        self.deleted.append(document_id)
        return True

    def reindex_document(self, document_id):
        self.reindexed.append(document_id)
        return SimpleNamespace(
            forced=True,
            model_changed=False,
            indexed_chunks=2,
            skipped_chunks=0,
        )

    def reindex_all(self):
        return (self.reindex_document(4),)

    def list_document_versions(self, document_id):
        return (
            SimpleNamespace(
                version_number=2,
                imported_at="2026-08-14 12:00:00",
                content_hash="a" * 64,
                chunk_count=2,
            ),
        )

    def list_stale_vectors(self):
        return ()

    def export_library_metadata(self, destination):
        self.exported.append(destination)
        return Path(destination)


class FakeVoiceListener:
    def __init__(self, texts):
        self.events = iter(
            SimpleNamespace(text=text)
            for text in texts
        )
        self.prime_count = 0

    def prime(self):
        self.prime_count += 1

    def wait_for_transcript(self, timeout):
        return next(self.events)


class FailingVoiceListener(FakeVoiceListener):
    def __init__(self):
        super().__init__([])

    def wait_for_transcript(self, timeout):
        raise RuntimeError("endpoint unavailable")


class InterruptingVoiceListener(FakeVoiceListener):
    def __init__(self):
        super().__init__([])

    def wait_for_transcript(self, timeout):
        raise KeyboardInterrupt


class ConversationLoopTests(unittest.TestCase):
    def test_loop_responds_clears_context_and_exits(self):
        agent = FakeAgent()
        speech = FakeSpeech()

        with patch(
            "builtins.input",
            side_effect=["Hallo", "/clear", "/exit"],
        ), patch("sys.stdout", new_callable=io.StringIO):
            run_conversation(agent, speech)

        self.assertEqual(["Hallo"], agent.requests)
        self.assertEqual(["Antwort auf: Hallo"], speech.spoken)
        self.assertEqual(1, agent.context.clear_count)

    def test_loop_recovers_from_brain_error(self):
        agent = FakeAgent()
        speech = FakeSpeech()
        agent.respond = lambda user_text: (_ for _ in ()).throw(
            RuntimeError("test failure")
        )

        with patch(
            "builtins.input",
            side_effect=["Hallo", "/exit"],
        ), patch("sys.stdout", new_callable=io.StringIO) as output:
            run_conversation(agent, speech)

        self.assertIn("Brain request failed", output.getvalue())
        self.assertEqual([], speech.spoken)

    def test_loop_manages_confirmed_memories(self):
        agent = FakeAgent()
        agent.memory_store = FakeMemoryStore()
        speech = FakeSpeech()

        with patch(
            "builtins.input",
            side_effect=[
                "/remember Vector Office AI ist mein Lieblingsprojekt.",
                "/memories",
                "/export-memories C:\\Backup\\memories.json",
                "/forget 3",
                "/exit",
            ],
        ), patch("sys.stdout", new_callable=io.StringIO) as output:
            run_conversation(agent, speech)

        self.assertEqual(
            ["Vector Office AI ist mein Lieblingsprojekt."],
            agent.memory_store.saved,
        )
        self.assertEqual([3], agent.memory_store.deleted)
        self.assertEqual(
            ["C:\\Backup\\memories.json"],
            agent.memory_store.exported,
        )
        self.assertIn("Memory 3 saved", output.getvalue())
        self.assertEqual([], speech.spoken)

    def test_loop_saves_explicit_style_feedback_separately(self):
        agent = FakeAgent()
        agent.memory_store = FakeMemoryStore()
        speech = FakeSpeech()

        with patch(
            "builtins.input",
            side_effect=["/feedback Bitte antworte ruhiger.", "/exit"],
        ), patch("sys.stdout", new_callable=io.StringIO) as output:
            run_conversation(agent, speech)

        self.assertEqual(
            [("Bitte antworte ruhiger.", "user-confirmed-feedback")],
            agent.memory_store.feedback,
        )
        self.assertIn("Feedback 3 saved", output.getvalue())
        self.assertEqual([], speech.spoken)

    def test_loop_manages_controlled_documents(self):
        agent = FakeAgent()
        agent.knowledge_library = FakeKnowledgeLibrary()
        speech = FakeSpeech()

        with patch(
            "builtins.input",
            side_effect=[
                "/learn C:\\Wissen\\projektwissen.md",
                "/documents",
                "/versions 4",
                "/stale-vectors",
                "/reindex 4",
                "/reindex-all",
                "/export-library C:\\Backup\\library.json",
                "/forget-document 4",
                "/exit",
            ],
        ), patch("sys.stdout", new_callable=io.StringIO) as output:
            run_conversation(agent, speech)

        self.assertEqual(
            ["C:\\Wissen\\projektwissen.md"],
            agent.knowledge_library.imported,
        )
        self.assertEqual([4], agent.knowledge_library.deleted)
        self.assertEqual([4, 4], agent.knowledge_library.reindexed)
        self.assertEqual(
            ["C:\\Backup\\library.json"],
            agent.knowledge_library.exported,
        )
        self.assertIn("Document 4 imported", output.getvalue())
        self.assertIn("Semantic index full: 2 indexed", output.getvalue())
        self.assertIn("Full library reindex completed", output.getvalue())
        self.assertIn("SHA-256", output.getvalue())
        self.assertIn("embeddinggemma@version-one", output.getvalue())
        self.assertIn("Document 4 v2", output.getvalue())
        self.assertIn("No stale vectors found", output.getvalue())
        self.assertIn("projektwissen", output.getvalue())
        self.assertEqual([], speech.spoken)

    def test_voice_loop_sends_transcript_to_agent_and_speech(self):
        agent = FakeAgent()
        speech = FakeSpeech()
        listener = FakeVoiceListener(["wie geht es dir heute"])

        with patch("sys.stdout", new_callable=io.StringIO):
            run_voice_conversation(
                agent,
                speech,
                listener,
                listen_timeout=1,
                max_turns=1,
            )

        self.assertEqual(1, listener.prime_count)
        self.assertEqual(["wie geht es dir heute"], agent.requests)
        self.assertEqual(
            ["Antwort auf: wie geht es dir heute"],
            speech.spoken,
        )

    def test_voice_loop_can_end_with_spoken_command(self):
        agent = FakeAgent()
        speech = FakeSpeech()
        listener = FakeVoiceListener(["vector beenden"])

        with patch("sys.stdout", new_callable=io.StringIO):
            run_voice_conversation(agent, speech, listener)

        self.assertEqual([], agent.requests)
        self.assertEqual([], speech.spoken)

    def test_voice_loop_accepts_german_spelling_of_vector_exit(self):
        agent = FakeAgent()
        speech = FakeSpeech()
        listener = FakeVoiceListener(["vektor beenden"])

        with patch("sys.stdout", new_callable=io.StringIO):
            run_voice_conversation(agent, speech, listener)

        self.assertEqual([], agent.requests)
        self.assertEqual([], speech.spoken)

    def test_voice_loop_handles_keyboard_interrupt_without_traceback(self):
        agent = FakeAgent()
        speech = FakeSpeech()

        with patch("sys.stdout", new_callable=io.StringIO) as output:
            run_voice_conversation(
                agent,
                speech,
                InterruptingVoiceListener(),
            )

        self.assertIn("Conversation ended", output.getvalue())
        self.assertEqual([], agent.requests)

    def test_voice_loop_stops_after_listener_failure(self):
        agent = FakeAgent()
        speech = FakeSpeech()
        listener = FailingVoiceListener()

        with patch("sys.stdout", new_callable=io.StringIO) as output:
            run_voice_conversation(agent, speech, listener)

        self.assertIn("Voice input failed", output.getvalue())
        self.assertEqual([], agent.requests)
        self.assertEqual([], speech.spoken)


if __name__ == "__main__":
    unittest.main()
