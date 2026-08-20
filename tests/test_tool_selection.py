"""Tests for exact, registry-bound conversational tool selection."""

import unittest
from unittest.mock import MagicMock

from tools.permissions import PermissionLevel
from tools.office import register_office_tools
from tools.project_checks import register_core_project_test_tool
from tools.project_status import register_project_status_tool
from tools.registry import ToolDefinition, ToolRegistry
from tools.selection import (
    ToolIntentRule,
    ToolIntentSelector,
    ToolSelectionStatus,
)
from tools.vector_actions import register_vector_action_tools


class DangerousTestTool:
    @property
    def definition(self):
        return ToolDefinition(
            "test.dangerous",
            "Never execute conversationally.",
            PermissionLevel.DANGEROUS,
        )

    def execute(self, _arguments):
        raise AssertionError("Dangerous tool must stay blocked.")


class ToolIntentSelectorTests(unittest.TestCase):
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
        self.registry = ToolRegistry()
        register_vector_action_tools(self.registry, self.actions)
        register_office_tools(self.registry)
        register_project_status_tool(self.registry)
        register_core_project_test_tool(self.registry)
        self.selector = ToolIntentSelector(self.registry)

    def test_exact_natural_phrase_selects_allowlisted_action(self):
        selection = self.selector.select("Bitte begrüße mich!")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("vector.perform_action", selection.tool_name)
        self.assertEqual("greeting", selection.arguments["action"])
        self.assertEqual(PermissionLevel.MUTATING, selection.permission)

    def test_additional_instruction_is_not_guessed(self):
        selection = self.selector.select("Begrüße mich und fahre vorwärts")

        self.assertEqual(ToolSelectionStatus.NO_MATCH, selection.status)

    def test_observed_vosk_lift_variant_selects_allowlisted_action(self):
        selection = self.selector.select("hebe deine lift")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("lift_up", selection.arguments["action"])

    def test_read_only_action_list_is_selected_from_registry(self):
        selection = self.selector.select("Welche Bewegungen kannst du?")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("vector.list_actions", selection.tool_name)
        self.assertEqual(PermissionLevel.READ_ONLY, selection.permission)

    def test_local_date_phrase_selects_fixed_read_only_mode(self):
        selection = self.selector.select("Welcher Tag ist heute?")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("office.local_datetime", selection.tool_name)
        self.assertEqual("date", selection.arguments["mode"])
        self.assertEqual(PermissionLevel.READ_ONLY, selection.permission)

    def test_project_status_selects_argument_free_read_only_tool(self):
        selection = self.selector.select("Wie ist der Projektstatus?")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("development.project_status", selection.tool_name)
        self.assertEqual({}, dict(selection.arguments))
        self.assertEqual(PermissionLevel.READ_ONLY, selection.permission)

    def test_project_test_selects_argument_free_mutating_tool(self):
        selection = self.selector.select("Projekt Test")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("development.run_core_tests", selection.tool_name)
        self.assertEqual({}, dict(selection.arguments))
        self.assertEqual(PermissionLevel.MUTATING, selection.permission)

    def test_project_test_word_variation_maps_to_same_fixed_tool(self):
        selection = self.selector.select("Bitte Projekt Tests ausführen")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("development.run_core_tests", selection.tool_name)

    def test_observed_vosk_project_test_variant_maps_to_fixed_tool(self):
        selection = self.selector.select("Projekte ist")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("development.run_core_tests", selection.tool_name)
        self.assertEqual({}, dict(selection.arguments))
        self.assertEqual(PermissionLevel.MUTATING, selection.permission)

    def test_observed_vosk_project_status_variant_is_selected(self):
        selection = self.selector.select("Wie ist der Projekt Status")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("development.project_status", selection.tool_name)

    def test_project_status_word_variation_maps_to_fixed_local_tool(self):
        selection = self.selector.select("Was sagt der Projekt Status aktuell")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("development.project_status", selection.tool_name)

    def test_observed_project_status_fragments_map_to_fixed_local_tool(self):
        phrases = (
            "Wie ist Ihr Projekt Status",
            "Ist der Projekt Status",
            "Wie ist das Projekt",
        )

        for phrase in phrases:
            with self.subTest(phrase=phrase):
                selection = self.selector.select(phrase)
                self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
                self.assertEqual("development.project_status", selection.tool_name)

    def test_observed_vosk_date_variant_selects_local_tool(self):
        selection = self.selector.select("Welchen Tag haben wir heute")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("office.local_datetime", selection.tool_name)
        self.assertEqual("date", selection.arguments["mode"])

    def test_ambiguous_datetime_question_is_blocked_from_model_fallback(self):
        selection = self.selector.select("Was für ein Datum ist heute")

        self.assertEqual(ToolSelectionStatus.BLOCKED, selection.status)
        self.assertIn("nicht eindeutig", selection.message)

    def test_missing_registered_target_is_blocked(self):
        rule = ToolIntentRule(("sicherer test",), "missing.tool", "Test")
        selector = ToolIntentSelector(ToolRegistry(), (rule,))

        selection = selector.select("sicherer test")

        self.assertEqual(ToolSelectionStatus.BLOCKED, selection.status)

    def test_dangerous_registered_target_is_blocked(self):
        registry = ToolRegistry()
        registry.register(DangerousTestTool())
        rule = ToolIntentRule(
            ("gefährlicher test",),
            "test.dangerous",
            "Gefahr",
        )
        selector = ToolIntentSelector(registry, (rule,))

        selection = selector.select("gefährlicher test")

        self.assertEqual(ToolSelectionStatus.BLOCKED, selection.status)

    def test_duplicate_normalized_phrases_are_rejected(self):
        rules = (
            ToolIntentRule(("Test",), "vector.list_actions", "A"),
            ToolIntentRule((" test! ",), "vector.list_actions", "B"),
        )

        with self.assertRaisesRegex(ValueError, "unique"):
            ToolIntentSelector(self.registry, rules)

    def test_empty_phrases_and_duplicate_arguments_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "phrases"):
            ToolIntentRule((), "vector.list_actions", "Liste")
        with self.assertRaisesRegex(ValueError, "argument names"):
            ToolIntentRule(
                ("test",),
                "vector.perform_action",
                "Test",
                (("action", "head_up"), ("action", "head_level")),
            )


if __name__ == "__main__":
    unittest.main()
