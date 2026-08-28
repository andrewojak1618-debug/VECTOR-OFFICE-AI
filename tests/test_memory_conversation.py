"""Tests für den kontrollierten gesprochenen Erinnerungsvorschlag."""

import io
import unittest
from unittest.mock import MagicMock, patch

from application.conversation import run_conversation, run_voice_conversation
from application.memory_conversation import (
    ControlledMemoryConversation,
    extract_memory_content,
)
from application.tool_conversation import ToolTurnStatus
from brain.agent import Agent
from memory.models import MemoryEntry
from tools.memory_write import (
    MAX_MEMORY_CONTENT_LENGTH,
    register_confirmed_memory_write_tool,
)
from tools.registry import ToolRegistry
from tools.vector_actions import register_vector_action_tools


class RejectingModel:
    def __init__(self):
        self.calls = 0

    def generate(self, _messages):
        self.calls += 1
        raise AssertionError("Memory intents must not invoke the model.")


class RecordingSpeech:
    def __init__(self):
        self.spoken = []

    def say(self, text, _style=None):
        self.spoken.append(text)
        return True


class OneTranscriptListener:
    def __init__(self, text):
        self.text = text
        self.timeouts = []

    def prime(self):
        return None

    def wait_for_transcript(self, timeout):
        self.timeouts.append(timeout)
        return type("Transcript", (), {"text": self.text})()


class ConfirmingFollowUp:
    def __init__(self):
        self.capture_timeouts = []

    def prepare(self):
        return True

    def capture(self, timeout, free_text=False):
        self.capture_timeouts.append(timeout)
        return "Ja, bitte."


class ControlledMemoryConversationTests(unittest.TestCase):
    def setUp(self):
        self.writer = MagicMock(side_effect=self._saved_entry)
        registry = ToolRegistry()
        register_confirmed_memory_write_tool(registry, self.writer)
        self.model = RejectingModel()
        self.agent = Agent(self.model, tool_registry=registry)
        self.controller = ControlledMemoryConversation(self.agent)

    @staticmethod
    def _saved_entry(content, **_values):
        return MemoryEntry(3, content, "fact", "user-confirmed-voice", "now")

    def test_explicit_request_waits_without_repeating_content(self):
        result = self.controller.handle(
            "Bitte merke dir, dass mein Lieblingsgetränk Tee ist.",
        )

        self.assertEqual(ToolTurnStatus.AWAITING_CONFIRMATION, result.status)
        self.assertTrue(self.controller.awaiting_confirmation)
        self.assertNotIn("Lieblingsgetränk", result.message)
        self.writer.assert_not_called()
        self.assertEqual(0, self.model.calls)

    def test_separate_yes_stores_exactly_once(self):
        self.controller.handle("Merke dir: Vector spricht Deutsch.")

        result = self.controller.handle("Ja, bitte speichern.")

        self.assertEqual(ToolTurnStatus.COMPLETED, result.status)
        self.assertFalse(self.controller.awaiting_confirmation)
        self.writer.assert_called_once()
        self.assertEqual("Vector spricht Deutsch.", self.writer.call_args.args[0])

    def test_rejection_and_cancellation_never_store(self):
        for response in ("Nein", "Abbrechen"):
            with self.subTest(response=response):
                self.controller.handle("Merke dir, Vector bleibt lokal.")
                result = self.controller.handle(response)
                self.assertEqual(ToolTurnStatus.CANCELLED, result.status)
                self.assertFalse(self.controller.awaiting_confirmation)
        self.writer.assert_not_called()

    def test_unrelated_and_invalid_requests_do_not_reach_storage(self):
        unrelated = self.controller.handle("Wie ist der Projektstatus?")
        invalid = self.controller.handle(
            "Merke dir " + "x" * (MAX_MEMORY_CONTENT_LENGTH + 1),
        )

        self.assertEqual(ToolTurnStatus.NOT_HANDLED, unrelated.status)
        self.assertEqual(ToolTurnStatus.BLOCKED, invalid.status)
        self.writer.assert_not_called()

    def test_voice_confirmation_uses_bounded_wakeword_free_window(self):
        listener = OneTranscriptListener("Merke dir, Vector spricht Deutsch.")
        follow_up = ConfirmingFollowUp()

        with patch("sys.stdout", new_callable=io.StringIO):
            run_voice_conversation(
                self.agent,
                RecordingSpeech(),
                listener,
                listen_timeout=30,
                max_turns=2,
                follow_up=follow_up,
                follow_up_timeout=5,
            )

        self.assertEqual([30], listener.timeouts)
        self.assertEqual([5], follow_up.capture_timeouts)
        self.writer.assert_called_once()
        self.assertEqual(0, self.model.calls)

    def test_emergency_stop_overrides_pending_memory(self):
        actions = MagicMock()
        actions.emergency_stop.return_value = True
        register_vector_action_tools(self.agent.tool_registry, actions)

        with patch(
            "builtins.input",
            side_effect=("Merke dir, Vector bleibt lokal.", "Stopp sofort", "/exit"),
        ), patch("sys.stdout", new_callable=io.StringIO):
            run_conversation(self.agent, RecordingSpeech())

        actions.emergency_stop.assert_called_once_with()
        self.writer.assert_not_called()

    def test_parser_preserves_content_after_supported_prefixes(self):
        self.assertEqual(
            "mein Name ist Andre.",
            extract_memory_content("Bitte merke dir, dass mein Name ist Andre."),
        )
        self.assertIsNone(extract_memory_content("Erinnere dich vielleicht daran."))

    def test_observed_wirepod_memory_prefix_is_recognized(self):
        for phrase in (
            "merkt ihr unser Codewort ist Nordlicht",
            "jacke dir unser Codewort ist Nordlicht",
            "merkel dir unser Codewort ist Nordlicht",
            "Erinnerung speichern: unser Codewort ist Nordlicht",
        ):
            with self.subTest(phrase=phrase):
                self.assertEqual(
                    "unser Codewort ist Nordlicht",
                    extract_memory_content(phrase),
                )


if __name__ == "__main__":
    unittest.main()
