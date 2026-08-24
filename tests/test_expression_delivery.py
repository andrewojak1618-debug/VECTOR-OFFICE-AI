"""Tests for sequential, explicitly confirmed expression delivery."""

import unittest

from application.expression_delivery import (
    ExpressionDeliveryStatus,
    ExpressionResponseCoordinator,
)
from brain.emotions import ConversationStance, EmotionalState, ExpressionCue
from brain.expression_actions import (
    ExpressionActionMapper,
    ExpressionActionSuggestion,
)
from brain.response_quality import SAFE_PROVIDER_REPLACEMENT
from tools.permissions import ToolAuthorization
from tools.proposals import ToolProposalReviewer
from tools.registry import ToolRegistry
from tools.vector_actions import register_vector_action_tools
from vector.speech import SpeechStyle


class RecordingActions:
    """Record test-only actions in their observed execution order."""

    def __init__(self, events: list[str], succeeds: bool = True):
        self.events = events
        self.succeeds = succeeds

    @staticmethod
    def available_actions() -> tuple[str, ...]:
        """Expose the production-compatible action aliases used by tests."""
        return ("greeting", "eyes_only", "reflective_expression")

    def perform(self, action: str) -> bool:
        """Record one action without accessing a physical robot."""
        self.events.append(f"action:{action}")
        return self.succeeds

    def emergency_stop(self) -> bool:
        """Reject unexpected emergency-stop use in this test boundary."""
        raise AssertionError("Expression delivery must not use emergency stop.")


class RecordingSpeech:
    """Record test speech without retaining it in delivery results."""

    def __init__(self, events: list[str], succeeds: bool = True):
        self.events = events
        self.succeeds = succeeds
        self.styles: list[SpeechStyle] = []

    def say(
        self,
        text: str,
        style: SpeechStyle = SpeechStyle.NEUTRAL,
    ) -> bool:
        """Record speech after any preceding animation."""
        self.events.append(f"speech:{text}")
        self.styles.append(style)
        return self.succeeds


class ExpressionResponseCoordinatorTests(unittest.TestCase):
    """Protect ordering, confirmation, privacy, and fallback behavior."""

    def setUp(self):
        self.events: list[str] = []
        self.actions = RecordingActions(self.events)
        self.registry = ToolRegistry()
        register_vector_action_tools(self.registry, self.actions)
        reviewer = ToolProposalReviewer(self.registry)
        self.mapper = ExpressionActionMapper(reviewer)
        self.speech = RecordingSpeech(self.events)
        self.coordinator = ExpressionResponseCoordinator(
            self.registry,
            self.speech,
        )

    def test_confirmed_animation_finishes_before_speech_starts(self):
        suggestion = self._suggest(ExpressionCue.REFLECTIVE)

        result = self.coordinator.deliver(
            "Eine kurze Antwort.",
            suggestion,
            ToolAuthorization(allow_mutation=True, confirmed=True),
        )

        self.assertEqual(
            ["action:reflective_expression", "speech:Eine kurze Antwort."],
            self.events,
        )
        self.assertEqual(
            ExpressionDeliveryStatus.ANIMATED_AND_SPOKEN,
            result.status,
        )
        self.assertEqual([SpeechStyle.REFLECTIVE], self.speech.styles)

    def test_declined_animation_keeps_reflective_speech_profile(self):
        suggestion = self._suggest(ExpressionCue.REFLECTIVE)

        result = self.coordinator.deliver(
            "Eine ruhige Antwort.",
            suggestion,
            animate=False,
        )

        self.assertEqual(["speech:Eine ruhige Antwort."], self.events)
        self.assertEqual([SpeechStyle.REFLECTIVE], self.speech.styles)
        self.assertEqual(ExpressionDeliveryStatus.SPOKEN_ONLY, result.status)
        self.assertIsNone(result.error_code)

    def test_missing_or_partial_confirmation_keeps_response_speech_only(self):
        suggestion = self._suggest(ExpressionCue.SUPPORTIVE)
        authorizations = (None, ToolAuthorization(allow_mutation=True))

        for authorization in authorizations:
            with self.subTest(authorization=authorization):
                self.events.clear()
                result = self.coordinator.deliver(
                    "Ruhige Antwort.",
                    suggestion,
                    authorization,
                )
                self.assertEqual(["speech:Ruhige Antwort."], self.events)
                self.assertEqual(
                    "expression_confirmation_required",
                    result.error_code,
                )
                self.assertEqual(SpeechStyle.SUPPORTIVE, self.speech.styles[-1])

    def test_action_failure_does_not_suppress_the_spoken_answer(self):
        self.actions.succeeds = False
        suggestion = self._suggest(ExpressionCue.ATTENTIVE)

        result = self.coordinator.deliver(
            "Sichere Antwort.",
            suggestion,
            ToolAuthorization(allow_mutation=True, confirmed=True),
        )

        self.assertEqual(
            ["action:eyes_only", "speech:Sichere Antwort."],
            self.events,
        )
        self.assertEqual(ExpressionDeliveryStatus.SPOKEN_ONLY, result.status)
        self.assertEqual("tool_execution_failed", result.error_code)
        self.assertEqual([SpeechStyle.CAUTIOUS], self.speech.styles)

    def test_non_expression_proposal_is_never_executed(self):
        review = ToolProposalReviewer(self.registry).resolve("vector.greeting")
        suggestion = ExpressionActionSuggestion(ExpressionCue.SUPPORTIVE, 3, review)

        result = self.coordinator.deliver(
            "Hallo.",
            suggestion,
            ToolAuthorization(allow_mutation=True, confirmed=True),
        )

        self.assertEqual(["speech:Hallo."], self.events)
        self.assertEqual("expression_proposal_invalid", result.error_code)

    def test_speech_failure_is_reported_without_retaining_private_text(self):
        secret = "private spoken answer"
        coordinator = ExpressionResponseCoordinator(
            self.registry,
            RecordingSpeech(self.events, succeeds=False),
        )

        result = coordinator.deliver(secret)

        self.assertEqual(ExpressionDeliveryStatus.SPEECH_FAILED, result.status)
        self.assertNotIn(secret, repr(result))

    def test_unreliable_text_is_replaced_at_expression_speech_boundary(self):
        result = self.coordinator.deliver("Internal Server Error")

        self.assertEqual(ExpressionDeliveryStatus.SPOKEN_ONLY, result.status)
        self.assertEqual([f"speech:{SAFE_PROVIDER_REPLACEMENT}"], self.events)

    def _suggest(self, cue: ExpressionCue) -> ExpressionActionSuggestion:
        stance = {
            ExpressionCue.ATTENTIVE: ConversationStance.CAUTIOUS,
            ExpressionCue.SUPPORTIVE: ConversationStance.SUPPORTIVE,
            ExpressionCue.REFLECTIVE: ConversationStance.REFLECTIVE,
        }[cue]
        state = EmotionalState(stance, 1, 2, "test", cue)
        return self.mapper.suggest(state)


if __name__ == "__main__":
    unittest.main()
