"""Integration tests for controlled tools in console and voice loops."""

import io
import json
import unittest
from unittest.mock import MagicMock, patch

from application.conversation import run_conversation, run_voice_conversation
from brain.agent import Agent
from tools.registry import ToolRegistry
from tools.vector_actions import register_vector_action_tools


EXPRESSIVE_ANSWER = (
    "Eine mögliche Perspektive ist, Freiheit als verantwortete Wahl zu verstehen."
)


class RejectingLanguageModel:
    def __init__(self):
        self.calls = 0

    def generate(self, _messages):
        self.calls += 1
        raise AssertionError("Tool intents must not invoke the language model.")


class FixedLanguageModel:
    def __init__(self, response=EXPRESSIVE_ANSWER):
        self.response = response
        self.calls = 0

    def generate(self, _messages):
        self.calls += 1
        return self.response


class FixedProposalModel(FixedLanguageModel):
    def __init__(self, proposal_id="vector.reflective_expression"):
        super().__init__(json.dumps({
            "schema_version": 1,
            "proposal_id": proposal_id,
        }))


class RecordingSpeech:
    def __init__(self):
        self.spoken = []

    def say(self, text, _style=None):
        self.spoken.append(text)
        return True


class RaisingSpeech(RecordingSpeech):
    def say(self, text, _style=None):
        self.spoken.append(text)
        raise RuntimeError("private Vector transport detail")


class TranscriptEvent:
    def __init__(self, text):
        self.text = text


class SequenceListener:
    def __init__(self, values):
        self.values = iter(values)
        self.primed = False
        self.timeouts = []

    def prime(self):
        self.primed = True

    def wait_for_transcript(self, timeout):
        self.timeouts.append(timeout)
        value = next(self.values)
        return None if value is None else TranscriptEvent(value)


class RecordingFollowUp:
    def __init__(self, prepared=True, transcripts=("ja",)):
        self.prepared = prepared
        self.transcripts = iter(transcripts)
        self.prepare_calls = 0
        self.capture_timeouts = []

    def prepare(self):
        self.prepare_calls += 1
        return self.prepared

    def capture(self, timeout):
        self.capture_timeouts.append(timeout)
        return next(self.transcripts)


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
            "reflective_expression",
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

    def test_output_failure_never_retries_confirmed_mutating_tool(self):
        speech = RaisingSpeech()

        with patch(
            "builtins.input",
            side_effect=["begrüße mich", "ja", "/exit"],
        ), patch("sys.stdout", new_callable=io.StringIO):
            run_conversation(self.agent, speech)

        self.actions.perform.assert_called_once_with("greeting")
        self.assertEqual(0, self.model.calls)

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

    def test_voice_uses_five_second_wakeword_free_confirmation_window(self):
        listener = SequenceListener(("schau bitte nach oben",))
        follow_up = RecordingFollowUp(
            transcripts=("Ja, bitte schau nach oben.",),
        )

        with patch("sys.stdout", new_callable=io.StringIO):
            run_voice_conversation(
                self.agent,
                self.speech,
                listener,
                listen_timeout=30,
                max_turns=2,
                follow_up=follow_up,
                follow_up_timeout=5,
            )

        self.assertEqual([30], listener.timeouts)
        self.assertEqual(1, follow_up.prepare_calls)
        self.assertEqual([5], follow_up.capture_timeouts)
        self.actions.perform.assert_called_once_with("head_up")

    def test_voice_confirmation_timeout_discards_pending_action(self):
        listener = SequenceListener(("schau nach oben", "vector beenden"))
        follow_up = RecordingFollowUp(transcripts=(None,))

        with patch("sys.stdout", new_callable=io.StringIO):
            run_voice_conversation(
                self.agent,
                self.speech,
                listener,
                listen_timeout=30,
                follow_up=follow_up,
                follow_up_timeout=5,
            )

        self.assertEqual([30, 30], listener.timeouts)
        self.assertEqual(1, follow_up.prepare_calls)
        self.assertEqual([5], follow_up.capture_timeouts)
        self.actions.perform.assert_not_called()

    def test_voice_trigger_failure_falls_back_to_normal_wakeword_wait(self):
        listener = SequenceListener(("schau nach oben", "ja"))
        follow_up = RecordingFollowUp(prepared=False)

        with patch("sys.stdout", new_callable=io.StringIO):
            run_voice_conversation(
                self.agent,
                self.speech,
                listener,
                listen_timeout=30,
                max_turns=2,
                follow_up=follow_up,
                follow_up_timeout=5,
            )

        self.assertEqual([30, 30], listener.timeouts)
        self.assertEqual(1, follow_up.prepare_calls)
        self.assertEqual([], follow_up.capture_timeouts)
        self.actions.perform.assert_called_once_with("head_up")

    def test_console_delivers_confirmed_expression_then_answer(self):
        model = FixedLanguageModel()
        agent = Agent(model, tool_registry=self.agent.tool_registry)

        with patch(
            "builtins.input",
            side_effect=["mit ausdruck was bedeutet freiheit", "ja", "/exit"],
        ), patch("sys.stdout", new_callable=io.StringIO):
            run_conversation(agent, self.speech)

        self.actions.perform.assert_called_once_with("reflective_expression")
        self.assertEqual(1, model.calls)
        self.assertEqual(2, len(self.speech.spoken))
        self.assertIn("Ja oder Nein", self.speech.spoken[0])
        self.assertEqual(EXPRESSIVE_ANSWER, self.speech.spoken[1])

    def test_voice_decline_delivers_answer_without_animation(self):
        model = FixedLanguageModel()
        agent = Agent(model, tool_registry=self.agent.tool_registry)
        listener = SequenceListener(
            ("mit ausdruck was bedeutet freiheit", "nein"),
        )

        with patch("sys.stdout", new_callable=io.StringIO):
            run_voice_conversation(
                agent,
                self.speech,
                listener,
                listen_timeout=1,
                max_turns=2,
            )

        self.actions.perform.assert_not_called()
        self.assertEqual(1, model.calls)
        self.assertEqual(EXPRESSIVE_ANSWER, self.speech.spoken[-1])

    def test_emergency_stop_discards_pending_expression(self):
        model = FixedLanguageModel()
        agent = Agent(model, tool_registry=self.agent.tool_registry)

        with patch(
            "builtins.input",
            side_effect=[
                "mit ausdruck was bedeutet freiheit",
                "stopp sofort",
                "/exit",
            ],
        ), patch("sys.stdout", new_callable=io.StringIO):
            run_conversation(agent, self.speech)

        self.actions.emergency_stop.assert_called_once_with()
        self.actions.perform.assert_not_called()
        self.assertNotIn(EXPRESSIVE_ANSWER, self.speech.spoken)

    def test_contextual_model_proposal_still_requires_spoken_yes(self):
        model = FixedProposalModel()
        agent = Agent(model, tool_registry=self.agent.tool_registry)

        with patch(
            "builtins.input",
            side_effect=[
                "schlage eine passende aktion vor: ich denke nach",
                "ja",
                "/exit",
            ],
        ), patch("sys.stdout", new_callable=io.StringIO):
            run_conversation(agent, self.speech)

        self.actions.perform.assert_called_once_with("reflective_expression")
        self.assertEqual(1, model.calls)
        self.assertEqual(2, len(self.speech.spoken))
        self.assertIn("Ja oder Nein", self.speech.spoken[0])

    def test_voice_accepts_context_in_separate_transcript(self):
        model = FixedProposalModel()
        agent = Agent(model, tool_registry=self.agent.tool_registry)
        listener = SequenceListener(
            ("welche aktion passt dazu", "ich denke nach", "ja"),
        )

        with patch("sys.stdout", new_callable=io.StringIO):
            run_voice_conversation(
                agent,
                self.speech,
                listener,
                listen_timeout=1,
                max_turns=3,
            )

        self.actions.perform.assert_called_once_with("reflective_expression")
        self.assertEqual(1, model.calls)
        self.assertIn("Kontext", self.speech.spoken[0])
        self.assertIn("Ja oder Nein", self.speech.spoken[1])


if __name__ == "__main__":
    unittest.main()
