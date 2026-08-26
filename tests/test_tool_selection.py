"""Tests for exact, registry-bound conversational tool selection."""

import unittest
from unittest.mock import MagicMock

from tools.code_quality_status import (
    CodeQualityStatus,
    register_code_quality_status_tool,
)
from tools.documentation_status import (
    DOCUMENT_COUNT,
    DocumentationStatus,
    register_documentation_status_tool,
)
from tools.changelog_status import register_latest_project_change_tool
from tools.permissions import PermissionLevel
from tools.library_status import register_local_library_status_tool
from tools.memory_status import register_local_memory_status_tool
from tools.office import register_office_tools
from tools.project_checks import register_core_project_test_tool
from tools.project_documents import (
    DOCUMENT_COUNT as PROJECT_DOCUMENT_COUNT,
    ProjectDocumentCatalogStatus,
    register_project_document_catalog_tool,
    register_project_document_open_tool,
)
from tools.project_status import register_project_status_tool
from tools.python_release import register_python_latest_version_tool
from tools.registry import ToolDefinition, ToolRegistry
from tools.research_source import register_fixed_research_source_tool
from tools.roadmap_status import register_next_roadmap_item_tool
from tools.service_status import register_local_service_status_tool
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
        register_code_quality_status_tool(
            self.registry,
            status_reader=lambda _root: CodeQualityStatus(90, 763, 0, 0, 0, 0, 0),
        )
        register_documentation_status_tool(
            self.registry,
            status_reader=lambda _root: DocumentationStatus(
                DOCUMENT_COUNT,
                0,
                0,
            ),
        )
        register_latest_project_change_tool(
            self.registry,
            reader=lambda _root: "kontrolliertes Werkzeug ergänzt",
        )
        register_project_document_catalog_tool(
            self.registry,
            status_reader=lambda _root: ProjectDocumentCatalogStatus(
                ("valid",) * PROJECT_DOCUMENT_COUNT,
            ),
        )
        register_project_document_open_tool(self.registry, opener=MagicMock())
        register_project_status_tool(self.registry)
        register_next_roadmap_item_tool(self.registry)
        register_fixed_research_source_tool(self.registry, lambda: True)
        register_python_latest_version_tool(self.registry, lambda: "3.14.7")
        register_core_project_test_tool(self.registry)
        register_local_service_status_tool(
            self.registry,
            lambda: True,
            lambda: True,
        )
        register_local_library_status_tool(self.registry, lambda: ())
        register_local_memory_status_tool(self.registry, lambda: None)
        self.selector = ToolIntentSelector(self.registry)

    def test_exact_natural_phrase_selects_allowlisted_action(self):
        selection = self.selector.select("Bitte begrüße mich!")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("vector.perform_action", selection.tool_name)
        self.assertEqual("greeting", selection.arguments["action"])
        self.assertEqual(PermissionLevel.MUTATING, selection.permission)

    def test_polite_head_phrase_selects_same_allowlisted_action(self):
        selection = self.selector.select("Schau bitte nach oben!")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("vector.perform_action", selection.tool_name)
        self.assertEqual("head_up", selection.arguments["action"])
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

    def test_system_status_selects_argument_free_read_only_tool(self):
        selection = self.selector.select("Wie ist der System Status?")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("system.local_service_status", selection.tool_name)
        self.assertEqual({}, dict(selection.arguments))
        self.assertEqual(PermissionLevel.READ_ONLY, selection.permission)

    def test_library_status_selects_argument_free_read_only_tool(self):
        selection = self.selector.select("Wie ist der Bibliothek Status?")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("knowledge.library_status", selection.tool_name)
        self.assertEqual({}, dict(selection.arguments))
        self.assertEqual(PermissionLevel.READ_ONLY, selection.permission)

    def test_memory_status_selects_argument_free_read_only_tool(self):
        selection = self.selector.select("Wie ist dein Gedächtnis Status?")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("memory.local_status", selection.tool_name)
        self.assertEqual({}, dict(selection.arguments))
        self.assertEqual(PermissionLevel.READ_ONLY, selection.permission)

    def test_project_status_selects_argument_free_read_only_tool(self):
        selection = self.selector.select("Wie ist der Projektstatus?")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("development.project_status", selection.tool_name)
        self.assertEqual({}, dict(selection.arguments))
        self.assertEqual(PermissionLevel.READ_ONLY, selection.permission)

    def test_documentation_status_selects_fixed_read_only_tool(self):
        selection = self.selector.select("Wie ist der Dokumentationsstatus?")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("development.documentation_status", selection.tool_name)
        self.assertEqual({}, dict(selection.arguments))
        self.assertEqual(PermissionLevel.READ_ONLY, selection.permission)

    def test_code_quality_status_selects_fixed_read_only_tool(self):
        selection = self.selector.select("Wie ist die Codequalität?")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("development.code_quality_status", selection.tool_name)
        self.assertEqual({}, dict(selection.arguments))
        self.assertEqual(PermissionLevel.READ_ONLY, selection.permission)

    def test_code_quality_word_variation_maps_to_fixed_tool(self):
        selection = self.selector.select("Code Qualität Status")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("development.code_quality_status", selection.tool_name)

    def test_observed_short_code_quality_phrase_maps_to_fixed_tool(self):
        selection = self.selector.select("Qualität Status")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("development.code_quality_status", selection.tool_name)

    def test_documentation_status_word_variation_maps_to_fixed_tool(self):
        selection = self.selector.select("Dokumentation Projekt Status")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("development.documentation_status", selection.tool_name)

    def test_project_document_catalog_selects_fixed_read_only_tool(self):
        selection = self.selector.select("Welche Projektdateien sind freigegeben?")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("development.project_document_catalog", selection.tool_name)
        self.assertEqual({}, dict(selection.arguments))
        self.assertEqual(PermissionLevel.READ_ONLY, selection.permission)

    def test_observed_split_project_files_phrase_selects_catalog(self):
        selection = self.selector.select("welche projekt dateien sind freigegeben")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("development.project_document_catalog", selection.tool_name)
        self.assertEqual({}, dict(selection.arguments))

    def test_open_roadmap_selects_fixed_mutating_document_tool(self):
        selection = self.selector.select("Öffne bitte die Roadmap")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("development.open_project_document", selection.tool_name)
        self.assertEqual({"document_id": "roadmap"}, dict(selection.arguments))
        self.assertEqual(PermissionLevel.MUTATING, selection.permission)

    def test_observed_polite_roadmap_order_selects_same_tool(self):
        selection = self.selector.select("Bitte öffne die Roadmap")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("development.open_project_document", selection.tool_name)
        self.assertEqual({"document_id": "roadmap"}, dict(selection.arguments))

    def test_observed_infinitive_split_roadmap_phrase_selects_same_tool(self):
        selection = self.selector.select("bitte öffnen road map")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("development.open_project_document", selection.tool_name)
        self.assertEqual({"document_id": "roadmap"}, dict(selection.arguments))

    def test_project_document_open_with_extra_target_is_blocked(self):
        selection = self.selector.select("Bitte öffnen Road Map und private Datei")

        self.assertEqual(ToolSelectionStatus.BLOCKED, selection.status)
        self.assertIn("nicht eindeutig", selection.message)

    def test_each_approved_document_has_one_fixed_open_intent(self):
        phrases = {
            "Öffne die Projektübersicht": "readme",
            "Öffne die Roadmap": "roadmap",
            "Öffne die Qualitätsregeln": "quality",
            "Öffne die Werkzeugsicherheit": "tool-security",
            "Öffne die Windows Startanleitung": "windows-startup",
            "Öffne die Firmware Sicherheitsregeln": "firmware-safety",
        }

        for phrase, identifier in phrases.items():
            with self.subTest(phrase=phrase):
                selection = self.selector.select(phrase)
                self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
                self.assertEqual({"document_id": identifier}, dict(selection.arguments))

    def test_latest_project_change_selects_fixed_read_only_tool(self):
        selection = self.selector.select("Was wurde zuletzt am Projekt geändert?")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("development.latest_change", selection.tool_name)
        self.assertEqual({}, dict(selection.arguments))
        self.assertEqual(PermissionLevel.READ_ONLY, selection.permission)

    def test_research_source_selects_argument_free_network_tool(self):
        selection = self.selector.select("Recherchequelle prüfen")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("research.python_source_status", selection.tool_name)
        self.assertEqual({}, dict(selection.arguments))
        self.assertEqual(PermissionLevel.NETWORK, selection.permission)

    def test_short_python_status_selects_fixed_network_source(self):
        selection = self.selector.select("Python Status")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("research.python_source_status", selection.tool_name)
        self.assertEqual({}, dict(selection.arguments))

    def test_python_version_selects_fixed_network_version_query(self):
        selection = self.selector.select("Welche Python Version ist aktuell?")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("research.python_latest_version", selection.tool_name)
        self.assertEqual(PermissionLevel.NETWORK, selection.permission)
        self.assertEqual({}, dict(selection.arguments))

    def test_observed_research_source_variant_selects_same_network_tool(self):
        selection = self.selector.select("Recherche Quelle überprüfen")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("research.python_source_status", selection.tool_name)
        self.assertEqual(PermissionLevel.NETWORK, selection.permission)

    def test_ambiguous_research_misrecognition_remains_unmatched(self):
        selection = self.selector.select("Schärfe Quellen überprüfen")

        self.assertEqual(ToolSelectionStatus.NO_MATCH, selection.status)

    def test_unclear_research_request_is_blocked_before_model_fallback(self):
        selection = self.selector.select(
            "Recherche Quelle Überprüfung von ergeht z",
        )

        self.assertEqual(ToolSelectionStatus.BLOCKED, selection.status)
        self.assertIn("Python Status", selection.message)

    def test_next_project_item_selects_fixed_read_only_tool(self):
        selection = self.selector.select("Was ist der nächste Projektpunkt?")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("development.next_roadmap_item", selection.tool_name)
        self.assertEqual({}, dict(selection.arguments))
        self.assertEqual(PermissionLevel.READ_ONLY, selection.permission)

    def test_next_project_item_word_variation_maps_to_fixed_tool(self):
        selection = self.selector.select("Welcher Punkt wäre als nächster dran")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("development.next_roadmap_item", selection.tool_name)

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
