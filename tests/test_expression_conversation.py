"""Tests for explicit two-turn expressive response requests."""

import unittest
from unittest.mock import MagicMock

from application.expression_conversation import (
    ControlledExpressionConversation,
    ExpressionTurnStatus,
)
from application.expression_delivery import (
    ExpressionDeliveryStatus,
    ExpressionResponseCoordinator,
)
from brain.agent import Agent
from brain.expression_actions import ExpressionActionMapper
from tools.proposals import ToolProposalReviewer
from tools.registry import ToolRegistry
from tools.vector_actions import register_vector_action_tools
from vector.speech import SpeechStyle


REFLECTIVE_ANSWER = (
    "Eine mögliche Perspektive ist, Freiheit als verantwortete Wahl zu verstehen."
)


class FixedLanguageModel:
    """Return one safe response while counting test requests."""

    def __init__(self, response: str = REFLECTIVE_ANSWER):
        self.response = response
        self.calls = 0

    def generate(self, _messages):
        """Return the configured test response."""
        self.calls += 1
        return self.response


class RecordingSpeech:
    """Record spoken messages in a shared event sequence."""

    def __init__(self, events: list[str]):
        self.events = events
        self.styles: list[SpeechStyle] = []

    def say(
        self,
        text: str,
        style: SpeechStyle = SpeechStyle.NEUTRAL,
    ) -> bool:
        """Record a successful speech operation."""
        self.events.append(f"speech:{text}")
        self.styles.append(style)
        return True


class ControlledExpressionConversationTests(unittest.TestCase):
    """Keep preparation, confirmation, and delivery clearly separated."""

    def setUp(self):
        self.events: list[str] = []
        self.actions = MagicMock()
        self.actions.available_actions.return_value = (
            "greeting",
            "eyes_only",
            "reflective_expression",
        )
        self.actions.perform.side_effect = self._perform
        self.registry = ToolRegistry()
        register_vector_action_tools(self.registry, self.actions)
        self.model = FixedLanguageModel()
        self.agent = Agent(self.model, tool_registry=self.registry)
        reviewer = ToolProposalReviewer(self.registry)
        self.speech = RecordingSpeech(self.events)
        self.controller = ControlledExpressionConversation(
            self.agent,
            ExpressionActionMapper(reviewer),
            ExpressionResponseCoordinator(
                self.registry,
                self.speech,
            ),
        )

    def test_explicit_request_waits_without_moving_or_speaking_answer(self):
        result = self.controller.handle("Mit Ausdruck was bedeutet Freiheit")

        self.assertEqual(
            ExpressionTurnStatus.AWAITING_CONFIRMATION,
            result.status,
        )
        self.assertTrue(self.controller.awaiting_confirmation)
        self.assertEqual([], self.events)
        self.actions.perform.assert_not_called()

    def test_separate_yes_runs_eyes_then_speaks_prepared_answer(self):
        self.controller.handle("Mit Ausdruck was bedeutet Freiheit")

        result = self.controller.handle("ja bitte")

        self.assertEqual(
            [f"action:reflective_expression", f"speech:{REFLECTIVE_ANSWER}"],
            self.events,
        )
        self.assertEqual(ExpressionTurnStatus.DELIVERED, result.status)
        self.assertEqual(
            ExpressionDeliveryStatus.ANIMATED_AND_SPOKEN,
            result.delivery.status,
        )
        self.assertFalse(self.controller.awaiting_confirmation)
        self.assertEqual([SpeechStyle.REFLECTIVE], self.speech.styles)

    def test_no_speaks_answer_without_animation(self):
        self.controller.handle("Antworte mit Ausdruck: Was bedeutet Freiheit?")

        result = self.controller.handle("nein")

        self.assertEqual([f"speech:{REFLECTIVE_ANSWER}"], self.events)
        self.actions.perform.assert_not_called()
        self.assertEqual([SpeechStyle.REFLECTIVE], self.speech.styles)
        self.assertEqual(ExpressionDeliveryStatus.SPOKEN_ONLY, result.delivery.status)

    def test_abort_discards_prepared_answer(self):
        self.controller.handle("Mit Ausdruck was bedeutet Freiheit")

        self.assertEqual(2, len(self.agent.context.history))

        result = self.controller.handle("abbrechen")

        self.assertEqual(ExpressionTurnStatus.CANCELLED, result.status)
        self.assertEqual([], self.events)
        self.assertFalse(self.controller.awaiting_confirmation)
        self.assertEqual((), self.agent.context.history)

    def test_observed_abort_variant_discards_prepared_answer(self):
        self.controller.handle("Mit Ausdruck was bedeutet Freiheit")

        result = self.controller.handle("abbruch")

        self.assertEqual(ExpressionTurnStatus.CANCELLED, result.status)
        self.assertFalse(self.controller.awaiting_confirmation)
        self.assertEqual((), self.agent.context.history)

    def test_external_safety_event_can_discard_pending_answer(self):
        self.controller.handle("Mit Ausdruck was bedeutet Freiheit")

        cancelled = self.controller.cancel_pending()
        later_yes = self.controller.handle("ja")

        self.assertTrue(cancelled)
        self.assertEqual(ExpressionTurnStatus.NOT_HANDLED, later_yes.status)
        self.assertEqual([], self.events)
        self.assertEqual((), self.agent.context.history)

    def test_neutral_cue_delivers_without_unnecessary_confirmation(self):
        result = self.controller.handle("Mit Ausdruck wie heißt du")

        self.assertEqual(ExpressionTurnStatus.DELIVERED, result.status)
        self.assertEqual([f"speech:{REFLECTIVE_ANSWER}"], self.events)
        self.actions.perform.assert_not_called()

    def test_ordinary_input_is_not_intercepted(self):
        result = self.controller.handle("Was bedeutet Freiheit?")

        self.assertEqual(ExpressionTurnStatus.NOT_HANDLED, result.status)
        self.assertEqual(0, self.model.calls)

    def test_missing_question_is_rejected_before_model_use(self):
        result = self.controller.handle("Mit Ausdruck")

        self.assertEqual(ExpressionTurnStatus.FAILED, result.status)
        self.assertEqual(0, self.model.calls)
        self.assertNotIn("Freiheit", result.message)

    def _perform(self, action: str) -> bool:
        self.events.append(f"action:{action}")
        return True


if __name__ == "__main__":
    unittest.main()
