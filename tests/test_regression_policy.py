"""Tests für die verbindliche und reproduzierbare Regressionsregel."""

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUALITY_DOCUMENT = PROJECT_ROOT / "docs" / "quality.md"
TESTING_DOCUMENT = PROJECT_ROOT / "docs" / "testing.md"


class RegressionPolicyTests(unittest.TestCase):
    def test_quality_rule_keeps_the_required_workflow(self):
        content = QUALITY_DOCUMENT.read_text(encoding="utf-8")

        self.assertIn(
            "Fehler reproduzieren → Regressionstest → Ursache beheben → "
            "Einzeltest → vollständige Testsuite → Live- oder Vector-Test",
            content,
        )

    def test_testing_rule_keeps_all_reproducible_acceptance_commands(self):
        content = TESTING_DOCUMENT.read_text(encoding="utf-8")
        commands = (
            "-m unittest discover -s tests -v",
            "-m compileall -q .",
            "-m mkdocs build --strict",
            "git diff --check",
        )

        for command in commands:
            with self.subTest(command=command):
                self.assertIn(command, content)

    def test_live_and_physical_tests_remain_separate_and_confirmed(self):
        content = TESTING_DOCUMENT.read_text(encoding="utf-8")

        self.assertIn("Live-Tests ersetzen niemals einen Regressionstest", content)
        self.assertIn("ausdrücklichen Bestätigung des Nutzers", content)


if __name__ == "__main__":
    unittest.main()
