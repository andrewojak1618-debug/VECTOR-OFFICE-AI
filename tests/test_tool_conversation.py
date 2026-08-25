"""Tests for confirmations and execution in controlled tool conversations."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from application.tool_conversation import (
    ControlledToolConversation,
    ToolTurnStatus,
)
from brain.agent import Agent
from memory.models import DocumentIndexStatus, KnowledgeDocument, MemoryStatistics
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
from tools.library_status import register_local_library_status_tool
from tools.memory_status import register_local_memory_status_tool
from tools.office import register_office_tools
from tools.project_checks import CoreTestSummary, register_core_project_test_tool
from tools.project_status import ProjectGitMetadata, register_project_status_tool
from tools.python_release import register_python_latest_version_tool
from tools.registry import ToolRegistry
from tools.research_source import register_fixed_research_source_tool
from tools.roadmap_status import register_next_roadmap_item_tool
from tools.service_status import register_local_service_status_tool
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
        register_project_status_tool(
            self.registry,
            Path("."),
            lambda _root: ProjectGitMetadata("main", "f04652f", 0),
            lambda _root: True,
        )
        register_next_roadmap_item_tool(
            self.registry,
            Path("."),
            lambda _root: "kontrollierten Dokumentationsstatus ergänzen",
        )
        self.research_checker = MagicMock(return_value=True)
        register_fixed_research_source_tool(
            self.registry,
            self.research_checker,
        )
        self.version_reader = MagicMock(return_value="3.14.7")
        register_python_latest_version_tool(self.registry, self.version_reader)
        self.test_runner = MagicMock(
            return_value=CoreTestSummary(True, 449, 4.1),
        )
        register_core_project_test_tool(
            self.registry,
            Path("."),
            Path("python.exe"),
            self.test_runner,
        )
        self.wirepod_status = MagicMock(return_value=True)
        self.ollama_status = MagicMock(return_value=True)
        register_local_service_status_tool(
            self.registry,
            self.wirepod_status,
            self.ollama_status,
        )
        self.library_status = MagicMock(return_value=(DocumentIndexStatus(
            KnowledgeDocument(1, "private.md", "Private", "a" * 64, "now"),
            1,
            3,
            "embeddinggemma",
            "version-one",
            768,
            3,
            0,
        ),))
        register_local_library_status_tool(self.registry, self.library_status)
        self.memory_status = MagicMock(return_value=MemoryStatistics(2, 1))
        register_local_memory_status_tool(self.registry, self.memory_status)
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

    def test_documentation_status_executes_without_model_or_confirmation(self):
        result = self.controller.handle("Dokumentation Status")

        self.assertEqual(ToolTurnStatus.COMPLETED, result.status)
        self.assertIn("Projektdokumentation ist vollständig", result.message)
        self.assertEqual(0, self.model.calls)

    def test_code_quality_status_executes_without_model_or_confirmation(self):
        result = self.controller.handle("Codequalität Status")

        self.assertEqual(ToolTurnStatus.COMPLETED, result.status)
        self.assertIn("Codequalität erfüllt die festen Regeln", result.message)
        self.assertIn("neunzig Module", result.message)
        self.assertEqual(0, self.model.calls)

    def test_observed_short_quality_status_never_reaches_model(self):
        result = self.controller.handle("Qualität Status")

        self.assertEqual(ToolTurnStatus.COMPLETED, result.status)
        self.assertIn("neunzig Module", result.message)
        self.assertEqual(0, self.model.calls)

    def test_latest_project_change_executes_without_model_or_confirmation(self):
        result = self.controller.handle("Projekt Änderung")

        self.assertEqual(ToolTurnStatus.COMPLETED, result.status)
        self.assertIn("kontrolliertes Werkzeug ergänzt", result.message)
        self.assertEqual(0, self.model.calls)

    def test_research_source_requires_separate_yes_before_network_use(self):
        proposed = self.controller.handle("Recherchequelle prüfen")

        self.assertEqual(ToolTurnStatus.AWAITING_CONFIRMATION, proposed.status)
        self.assertIn("einmaliger Internetzugriff", proposed.message)
        self.research_checker.assert_not_called()

        completed = self.controller.handle("Ja")

        self.assertEqual(ToolTurnStatus.COMPLETED, completed.status)
        self.assertIn("Python-Quelle ist erreichbar", completed.message)
        self.research_checker.assert_called_once_with()
        self.assertEqual(0, self.model.calls)

    def test_observed_research_variant_still_waits_before_network_use(self):
        proposed = self.controller.handle("Recherche Quelle überprüfen")

        self.assertEqual(ToolTurnStatus.AWAITING_CONFIRMATION, proposed.status)
        self.research_checker.assert_not_called()

    def test_python_version_requires_yes_and_bypasses_language_model(self):
        proposed = self.controller.handle("Python Version")

        self.assertEqual(ToolTurnStatus.AWAITING_CONFIRMATION, proposed.status)
        self.assertIn("einmaliger Internetzugriff", proposed.message)
        self.version_reader.assert_not_called()

        completed = self.controller.handle("Ja")

        self.assertEqual(ToolTurnStatus.COMPLETED, completed.status)
        self.assertIn("3 Punkt 14 Punkt 7", completed.message)
        self.version_reader.assert_called_once_with()
        self.assertEqual(0, self.model.calls)

    def test_unclear_research_request_never_reaches_language_model(self):
        result = self.controller.handle(
            "Recherche Quelle Überprüfung von ergeht z",
        )

        self.assertEqual(ToolTurnStatus.BLOCKED, result.status)
        self.assertIn("Python Status", result.message)
        self.research_checker.assert_not_called()
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

    def test_next_project_item_executes_without_model_or_confirmation(self):
        result = self.controller.handle("Was ist der nächste Projektpunkt?")

        self.assertEqual(ToolTurnStatus.COMPLETED, result.status)
        self.assertIn("kontrollierten Dokumentationsstatus", result.message)
        self.assertEqual(0, self.model.calls)

    def test_system_status_executes_locally_without_confirmation_or_model(self):
        result = self.controller.handle("System Status")

        self.assertEqual(ToolTurnStatus.COMPLETED, result.status)
        self.assertIn("WirePod ist lokal verfügbar", result.message)
        self.assertIn("Ollama ist lokal verfügbar", result.message)
        self.wirepod_status.assert_called_once()
        self.ollama_status.assert_called_once()
        self.assertEqual(0, self.model.calls)

    def test_library_status_exposes_counts_without_model_or_confirmation(self):
        result = self.controller.handle("Bibliothek Status")

        self.assertEqual(ToolTurnStatus.COMPLETED, result.status)
        self.assertIn("1 Dokument", result.message)
        self.assertIn("3 Abschnitten", result.message)
        self.assertNotIn("Private", result.message)
        self.library_status.assert_called_once()
        self.assertEqual(0, self.model.calls)

    def test_memory_status_exposes_counts_without_model_or_confirmation(self):
        result = self.controller.handle("Gedächtnis Status")

        self.assertEqual(ToolTurnStatus.COMPLETED, result.status)
        self.assertIn("2 bestätigte Erinnerungen", result.message)
        self.assertIn("ein bestätigtes Stil-Feedback", result.message)
        self.memory_status.assert_called_once()
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

    def test_natural_affirmative_sentence_confirms_pending_action(self):
        self.controller.handle("schau nach oben")

        completed = self.controller.handle("Ja, bitte schau nach oben.")

        self.assertEqual(ToolTurnStatus.COMPLETED, completed.status)
        self.actions.perform.assert_called_once_with("head_up")

    def test_affirmative_sentence_with_cancellation_never_executes(self):
        self.controller.handle("schau nach oben")

        cancelled = self.controller.handle("Ja, doch nicht ausführen.")

        self.assertEqual(ToolTurnStatus.CANCELLED, cancelled.status)
        self.actions.perform.assert_not_called()

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
