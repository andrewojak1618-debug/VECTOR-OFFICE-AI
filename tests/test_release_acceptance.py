"""Tests for controlled release acceptance and local backup restoration."""

import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from diagnostics.release_acceptance import (
    AcceptanceResult,
    build_checks,
    run_checks,
    write_report,
)
from memory.database import SQLiteMemoryStore
from memory.library import SQLiteKnowledgeLibrary


class ReleaseAcceptanceTests(unittest.TestCase):
    def test_default_acceptance_contains_only_core_checks(self):
        checks = build_checks("python")

        self.assertEqual(4, len(checks))
        self.assertEqual({"core"}, {check.category for check in checks})

    def test_live_checks_are_added_only_when_requested(self):
        checks = build_checks(
            "python",
            live_ollama=True,
            live_openai=True,
        )

        categories = [check.category for check in checks]
        self.assertEqual(3, categories.count("live-ollama"))
        self.assertEqual(1, categories.count("live-openai"))
        self.assertNotIn("physical-vector", categories)

    def test_focused_regression_precedes_complete_suite(self):
        checks = build_checks(
            "python",
            regression_test=(
                "tests.test_release_acceptance."
                "ReleaseAcceptanceTests.test_default_acceptance_contains_only_core_checks"
            ),
        )

        self.assertEqual("regression", checks[0].category)
        self.assertEqual("Focused regression test", checks[0].name)
        self.assertEqual("Complete unit test suite", checks[1].name)

    def test_regression_target_must_stay_below_tests(self):
        invalid_targets = (
            "diagnostics.release_acceptance",
            "tests/test_release_acceptance.py",
            "tests.test_release_acceptance;whoami",
        )

        for target in invalid_targets:
            with self.subTest(target=target):
                with self.assertRaisesRegex(ValueError, "dotted target"):
                    build_checks("python", regression_test=target)

    def test_physical_checks_require_explicit_confirmation(self):
        with self.assertRaisesRegex(ValueError, "explicit confirmation"):
            build_checks("python", physical_vector=True)

        checks = build_checks(
            "python",
            physical_vector=True,
            physical_confirmed=True,
        )
        physical = [item for item in checks if item.category == "physical-vector"]
        self.assertEqual(2, len(physical))

    def test_runner_continues_after_failure_and_reports_each_result(self):
        checks = build_checks("python")[:2]
        return_codes = iter((1, 0))

        with redirect_stdout(io.StringIO()):
            results = run_checks(
                checks,
                executor=lambda _check: next(return_codes),
            )

        self.assertEqual((False, True), tuple(result.passed for result in results))
        self.assertEqual((1, 0), tuple(result.return_code for result in results))

    def test_report_contains_metadata_but_no_commands_or_output(self):
        result = AcceptanceResult("Safe check", "core", True, 0, 0.1)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_report(Path(temp_dir) / "acceptance.json", (result,))
            payload = json.loads(path.read_text(encoding="utf-8"))
            encoded = path.read_text(encoding="utf-8")

        self.assertTrue(payload["passed"])
        self.assertEqual("Safe check", payload["results"][0]["name"])
        self.assertNotIn("command", encoded)
        self.assertNotIn("output", encoded)

    def test_running_copy_backup_restores_memory_and_document(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            database = root / "vector.db"
            backup = root / "vector.backup.db"
            document = root / "fact.md"
            document.write_text("Projektstatus: stabil", encoding="utf-8")
            SQLiteMemoryStore(database).remember("Der Nutzer bevorzugt Deutsch.")
            SQLiteKnowledgeLibrary(database).import_document(document)
            shutil.copy2(database, backup)
            database.unlink()
            shutil.copy2(backup, database)

            memories = SQLiteMemoryStore(database).list_memories()
            documents = SQLiteKnowledgeLibrary(database).list_documents()

        self.assertEqual("Der Nutzer bevorzugt Deutsch.", memories[0].content)
        self.assertEqual("fact", documents[0].title)


if __name__ == "__main__":
    unittest.main()
