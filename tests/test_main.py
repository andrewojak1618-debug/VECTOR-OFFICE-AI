import io
import unittest
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
        self.deleted = []

    def remember(self, content):
        self.saved.append(content)
        return SimpleNamespace(id=3, content=content)

    def list_memories(self):
        return (SimpleNamespace(id=3, content=self.saved[-1]),)

    def forget(self, memory_id):
        self.deleted.append(memory_id)
        return True


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
        self.assertIn("Memory 3 saved", output.getvalue())
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


if __name__ == "__main__":
    unittest.main()
