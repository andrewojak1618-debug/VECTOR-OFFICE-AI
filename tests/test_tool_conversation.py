"""Tests for confirmations and execution in controlled tool conversations."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from application.tool_conversation import (
    ControlledToolConversation,
    ToolTurnStatus,
)
from brain.agent import Agent
from tools.office import register_office_tools
from tools.project_checks import CoreTestSummary, register_core_project_test_tool
from tools.project_status import ProjectGitMetadata, register_project_status_tool
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
        register_office_tools(self.registry)
        register_project_status_tool(
            self.registry,
            Path("."),
            lambda _root: ProjectGitMetadata("main", "f04652f", 0),
            lambda _root: True,
        )
        self.test_runner = MagicMock(
            return_value=CoreTestSummary(True, 449, 4.1),
        )
        register_core_project_test_tool(
            self.registry,
            Path("."),
            Path("python.exe"),
            self.test_runner,
        )
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

    def test_local_time_executes_without_model_or_confirmation(self):
        result = self.controller.handle("Wie spät ist es?")

        self.assertEqual(ToolTurnStatus.COMPLETED, result.status)
        self.assertTrue(result.message.startswith("Es ist "))
        self.assertTrue(result.execution.succeeded)
        self.actions.perform.assert_not_called()
        self.assertEqual(0, self.model.calls)

    def test_ambiguous_date_question_never_reaches_language_model(self):
        result = self.controller.handle("Was für ein Datum ist heute?")

        self.assertEqual(ToolTurnStatus.BLOCKED, result.status)
        self.assertIn("nicht eindeutig", result.message)
        self.assertEqual(0, self.model.calls)

    def test_project_status_executes_without_model_or_confirmation(self):
        result = self.controller.handle("Wie ist der Projektstatus?")

        self.assertEqual(ToolTurnStatus.COMPLETED, result.status)
        self.assertIn("Branch main", result.message)
        self.assertIn("keine offenen Änderungen", result.message)
        self.assertEqual(0, self.model.calls)

    def test_project_status_variation_executes_without_language_model(self):
        result = self.controller.handle("Was sagt der Projekt Status aktuell?")

        self.assertEqual(ToolTurnStatus.COMPLETED, result.status)
        self.assertIn("Branch main", result.message)
        self.assertEqual(0, self.model.calls)

    def test_project_tests_require_yes_and_never_use_language_model(self):
        proposed = self.controller.handle("Projekt Test")

        self.assertEqual(ToolTurnStatus.AWAITING_CONFIRMATION, proposed.status)
        self.test_runner.assert_not_called()

        completed = self.controller.handle("Ja")

        self.assertEqual(ToolTurnStatus.COMPLETED, completed.status)
        self.assertIn("400 Tests und weitere 49 Tests", completed.message)
        self.test_runner.assert_called_once()
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
