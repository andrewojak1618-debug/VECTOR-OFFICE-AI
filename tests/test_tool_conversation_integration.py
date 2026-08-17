"""Integration tests for controlled tools in console and voice loops."""

import io
import unittest
from unittest.mock import MagicMock, patch

from application.conversation import run_conversation, run_voice_conversation
from brain.agent import Agent
from tools.registry import ToolRegistry
from tools.vector_actions import register_vector_action_tools


class RejectingLanguageModel:
    def __init__(self):
        self.calls = 0

    def generate(self, _messages):
        self.calls += 1
        raise AssertionError("Tool intents must not invoke the language model.")


class RecordingSpeech:
    def __init__(self):
        self.spoken = []

    def say(self, text):
        self.spoken.append(text)
        return True


class TranscriptEvent:
    def __init__(self, text):
        self.text = text


class SequenceListener:
    def __init__(self, values):
        self.values = iter(values)
        self.primed = False

    def prime(self):
        self.primed = True

    def wait_for_transcript(self, _timeout):
        return TranscriptEvent(next(self.values))


class ToolConversationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.actions = MagicMock()
        self.actions.available_actions.return_value = (
            "head_up",
            "head_level",
            "lift_up",
            "lift_down",
            "greeting",
            "eyes_only",
        )
        self.actions.perform.return_value = True
        self.actions.emergency_stop.return_value = True
        registry = ToolRegistry()
        register_vector_action_tools(registry, self.actions)
        self.model = RejectingLanguageModel()
        self.agent = Agent(self.model, tool_registry=registry)
        self.speech = RecordingSpeech()

    def test_console_keeps_confirmation_without_model_execution(self):
        with patch(
            "builtins.input",
            side_effect=["begrüße mich", "ja", "/exit"],
        ), patch("sys.stdout", new_callable=io.StringIO):
            run_conversation(self.agent, self.speech)

        self.actions.perform.assert_called_once_with("greeting")
        self.assertEqual(0, self.model.calls)
        self.assertEqual(2, len(self.speech.spoken))
        self.assertIn("Ja oder Nein", self.speech.spoken[0])

    def test_voice_keeps_confirmation_across_two_transcripts(self):
        listener = SequenceListener(("schau nach oben", "ja"))

        with patch("sys.stdout", new_callable=io.StringIO):
            run_voice_conversation(
                self.agent,
                self.speech,
                listener,
                listen_timeout=1,
                max_turns=2,
            )

        self.assertTrue(listener.primed)
        self.actions.perform.assert_called_once_with("head_up")
        self.assertEqual(0, self.model.calls)
        self.assertEqual(2, len(self.speech.spoken))


if __name__ == "__main__":
    unittest.main()
