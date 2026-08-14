import io
import unittest
from unittest.mock import patch

from main import run_conversation


class FakeContext:
    def __init__(self):
        self.clear_count = 0

    def clear(self):
        self.clear_count += 1


class FakeAgent:
    def __init__(self):
        self.context = FakeContext()
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


if __name__ == "__main__":
    unittest.main()
