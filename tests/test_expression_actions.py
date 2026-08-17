"""Tests for non-executing expression-cue action suggestions."""

import unittest
from unittest.mock import MagicMock

from brain.emotions import ConversationStance, EmotionalState, ExpressionCue
from brain.expression_actions import (
    EXPRESSION_PROPOSAL_IDS,
    ExpressionActionMapper,
)
from tools.proposals import ToolProposalReviewer, ToolProposalStatus
from tools.registry import ToolRegistry
from tools.vector_actions import register_vector_action_tools


class ExpressionActionMapperTests(unittest.TestCase):
    """Keep simulated stance metadata outside the execution boundary."""

    def setUp(self):
        self.events = []
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
        registry = ToolRegistry(audit_sink=self.events.append)
        register_vector_action_tools(registry, self.actions)
        self.mapper = ExpressionActionMapper(ToolProposalReviewer(registry))

    def test_neutral_state_produces_no_action_proposal(self):
        suggestion = self.mapper.suggest(self._state(ExpressionCue.NEUTRAL, 0))

        self.assertEqual(ToolProposalStatus.NO_PROPOSAL, suggestion.review.status)
        self.assertFalse(suggestion.proposed)

    def test_non_neutral_cues_use_only_fixed_expression_profiles(self):
        expected = {
            ExpressionCue.ATTENTIVE: "eyes_only",
            ExpressionCue.SUPPORTIVE: "eyes_only",
            ExpressionCue.REFLECTIVE: "reflective_expression",
        }

        for cue, action in expected.items():
            with self.subTest(cue=cue):
                suggestion = self.mapper.suggest(self._state(cue, 1))
                self.assertTrue(suggestion.proposed)
                self.assertEqual(
                    action,
                    suggestion.review.proposal.arguments["action"],
                )

    def test_mapping_never_executes_or_authorizes_a_tool(self):
        suggestion = self.mapper.suggest(
            self._state(ExpressionCue.REFLECTIVE, 2)
        )

        self.assertTrue(suggestion.proposed)
        self.actions.perform.assert_not_called()
        self.actions.emergency_stop.assert_not_called()
        self.assertEqual([], self.events)

    def test_unavailable_registry_target_is_blocked(self):
        mapper = ExpressionActionMapper(ToolProposalReviewer(ToolRegistry()))

        suggestion = mapper.suggest(self._state(ExpressionCue.ATTENTIVE, 1))

        self.assertEqual(ToolProposalStatus.REJECTED, suggestion.review.status)
        self.assertEqual(
            "proposal_target_unavailable",
            suggestion.review.error_code,
        )

    def test_zero_intensity_and_sensitive_reason_are_not_propagated(self):
        secret = "private-user-sentence"
        state = self._state(ExpressionCue.SUPPORTIVE, 0, reason=secret)

        suggestion = self.mapper.suggest(state)

        self.assertEqual(ToolProposalStatus.NO_PROPOSAL, suggestion.review.status)
        self.assertNotIn(secret, repr(suggestion))

    def test_mapping_covers_every_expression_cue(self):
        self.assertEqual(set(ExpressionCue), set(EXPRESSION_PROPOSAL_IDS))
        self.assertNotIn("vector.greeting", EXPRESSION_PROPOSAL_IDS.values())

    @staticmethod
    def _state(cue: ExpressionCue, intensity: int, reason: str = "test"):
        stance = {
            ExpressionCue.NEUTRAL: ConversationStance.NEUTRAL,
            ExpressionCue.ATTENTIVE: ConversationStance.CAUTIOUS,
            ExpressionCue.SUPPORTIVE: ConversationStance.SUPPORTIVE,
            ExpressionCue.REFLECTIVE: ConversationStance.REFLECTIVE,
        }[cue]
        return EmotionalState(stance, intensity, 7, reason, cue)


if __name__ == "__main__":
    unittest.main()
