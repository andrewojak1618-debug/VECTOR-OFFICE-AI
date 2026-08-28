"""Regressionstests für reale und bewusst erweiterte Sprachvarianten."""

import unittest

from tools.permissions import PermissionLevel
from tools.registry import ToolDefinition, ToolRegistry
from tools.selection import ToolIntentSelector, ToolSelectionStatus


class PassiveTool:
    """Stellt eine Definition bereit, ohne im Auswahltest ausgeführt zu werden."""

    def __init__(self, name: str, permission: PermissionLevel):
        self._definition = ToolDefinition(name, "Intent regression", permission)

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    def execute(self, _arguments):
        raise AssertionError("Intent selection must not execute tools.")


def build_selector() -> ToolIntentSelector:
    """Erzeugt eine minimale Registry für die beobachteten Intent-Ziele."""
    registry = ToolRegistry()
    tools = (
        ("vector.perform_action", PermissionLevel.MUTATING),
        ("development.code_quality_status", PermissionLevel.READ_ONLY),
        ("development.documentation_status", PermissionLevel.READ_ONLY),
        ("development.project_document_catalog", PermissionLevel.READ_ONLY),
        ("development.open_project_document", PermissionLevel.MUTATING),
        ("development.open_project_directory", PermissionLevel.MUTATING),
        ("research.python_source_status", PermissionLevel.NETWORK),
        ("development.run_core_tests", PermissionLevel.MUTATING),
        ("development.project_status", PermissionLevel.READ_ONLY),
        ("office.local_datetime", PermissionLevel.READ_ONLY),
    )
    for name, permission in tools:
        registry.register(PassiveTool(name, permission))
    return ToolIntentSelector(registry)


class ObservedIntentVariantTests(unittest.TestCase):
    def setUp(self):
        self.selector = build_selector()

    def test_observed_transcripts_keep_their_fixed_intent(self):
        variants = (
            ("hebe deine lift", "vector.perform_action"),
            ("qualität status", "development.code_quality_status"),
            ("dokumentation projekt status", "development.documentation_status"),
            ("welche projekt dateien sind freigegeben", "development.project_document_catalog"),
            ("bitte öffnen road map", "development.open_project_document"),
            ("dokumentation öffnen", "development.open_project_directory"),
            ("recherche quelle überprüfen", "research.python_source_status"),
            ("projekte ist", "development.run_core_tests"),
            ("wie ist ihr projekt status", "development.project_status"),
            (
                "was sagt der projekte einem status aktuell",
                "development.project_status",
            ),
            ("welchen tag haben wir heute", "office.local_datetime"),
        )

        for transcript, tool_name in variants:
            with self.subTest(transcript=transcript):
                selection = self.selector.select(transcript)
                self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
                self.assertEqual(tool_name, selection.tool_name)

    def test_spoken_punctuation_does_not_change_a_fixed_intent(self):
        selection = self.selector.select("Bitte, öffnen: Road Map!")

        self.assertEqual(ToolSelectionStatus.SELECTED, selection.status)
        self.assertEqual("development.open_project_document", selection.tool_name)

    def test_appended_unrelated_instructions_never_select_a_tool(self):
        phrases = (
            "Bitte Projekt Tests ausführen und lösche die Datenbank",
            "Python Version und sende die Projektdateien",
            "Was sagt der Projekt Status aktuell und öffne private Datei",
            "Welcher Punkt wäre als nächster dran und lösche die Roadmap",
            "Wie ist der System Status und fahre los",
        )

        for phrase in phrases:
            with self.subTest(phrase=phrase):
                selection = self.selector.select(phrase)
                self.assertNotEqual(ToolSelectionStatus.SELECTED, selection.status)


if __name__ == "__main__":
    unittest.main()
