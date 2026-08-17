"""Tests for confirmations and execution in controlled tool conversations."""

import unittest
from unittest.mock import MagicMock

from application.tool_conversation import (
    ControlledToolConversation,
    ToolTurnStatus,
)
from brain.agent import Agent
from tools.registry import ToolRegistry
from tools.selection import ToolIntentSelector
from tools.vector_actions import register_vector_action_tools


class UnusedLanguageModel:
    def __init__(self):
        self.calls = 0

    def generate(self, _messages):
        self.calls += 1
        return "Das Modell darf für Tools nicht verwendet werden."


class ControlledToolConversationTests(unittest.TestCase):
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
        self.registry = ToolRegistry()
        register_vector_action_tools(self.registry, self.actions)
        self.model = UnusedLanguageModel()
        self.agent = Agent(self.model, tool_registry=self.registry)
        self.controller = ControlledToolConversation(
            self.agent,
            ToolIntentSelector(self.registry),
        )

    def test_read_only_tool_executes_without_confirmation(self):
        result = self.controller.handle("welche aktionen kannst du")

        self.assertEqual(ToolTurnStatus.COMPLETED, result.status)
        self.assertIn("head_up", result.message)
        self.actions.perform.assert_not_called()
        self.assertEqual(0, self.model.calls)

    def test_mutating_action_waits_for_explicit_yes(self):
        proposed = self.controller.handle("begrüße mich")

        self.assertEqual(ToolTurnStatus.AWAITING_CONFIRMATION, proposed.status)
        self.actions.perform.assert_not_called()

        completed = self.controller.handle("ja bitte")

        self.assertEqual(ToolTurnStatus.COMPLETED, completed.status)
        self.actions.perform.assert_called_once_with("greeting")
        self.assertEqual(0, self.model.calls)

    def test_unknown_confirmation_keeps_action_pending(self):
        self.controller.handle("schau nach oben")

        result = self.controller.handle("vielleicht später")

        self.assertEqual(ToolTurnStatus.AWAITING_CONFIRMATION, result.status)
        self.actions.perform.assert_not_called()

    def test_no_cancels_pending_action(self):
        self.controller.handle("lift nach oben")

        cancelled = self.controller.handle("nein")
        ordinary = self.controller.handle("normale frage")

        self.assertEqual(ToolTurnStatus.CANCELLED, cancelled.status)
        self.assertEqual(ToolTurnStatus.NOT_HANDLED, ordinary.status)
        self.actions.perform.assert_not_called()

    def test_observed_abort_variant_cancels_pending_action(self):
        self.controller.handle("lift nach oben")

        cancelled = self.controller.handle("abbruch")

        self.assertEqual(ToolTurnStatus.CANCELLED, cancelled.status)
        self.actions.perform.assert_not_called()

    def test_emergency_stop_overrides_pending_confirmation(self):
        self.controller.handle("begrüße mich")

        stopped = self.controller.handle("stopp sofort")

        self.assertEqual(ToolTurnStatus.COMPLETED, stopped.status)
        self.assertFalse(stopped.speak)
        self.actions.emergency_stop.assert_called_once_with()
        self.actions.perform.assert_not_called()

    def test_unmatched_text_is_left_for_normal_conversation(self):
        result = self.controller.handle("Wie wird das Wetter?")

        self.assertEqual(ToolTurnStatus.NOT_HANDLED, result.status)
        self.assertEqual(0, self.model.calls)


if __name__ == "__main__":
    unittest.main()
