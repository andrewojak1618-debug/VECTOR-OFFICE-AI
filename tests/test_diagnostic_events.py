"""Privacy and retention tests for structured local runtime diagnostics."""

import json
import tempfile
import unittest
from pathlib import Path

from diagnostics.events import DiagnosticLevel, StructuredDiagnosticReporter


class StructuredDiagnosticReporterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "events.jsonl"

    def tearDown(self):
        self.temporary.cleanup()

    def test_event_uses_stable_schema_and_safe_metadata(self):
        reporter = StructuredDiagnosticReporter(self.path)

        self.assertTrue(reporter.emit(
            DiagnosticLevel.INFO,
            "ollama",
            "request.completed",
            attempt=1,
            max_attempts=2,
            status="success",
        ))

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(1, payload["schema_version"])
        self.assertEqual("info", payload["level"])
        self.assertEqual("ollama", payload["component"])
        self.assertEqual("request.completed", payload["code"])
        self.assertEqual(1, payload["details"]["attempt"])
        self.assertIn("+00:00", payload["occurred_at"])

    def test_private_content_fields_are_rejected(self):
        reporter = StructuredDiagnosticReporter(self.path)

        for field in ("transcript", "prompt", "response", "api_key", "document"):
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError,
                "forbidden field",
            ):
                reporter.emit(
                    DiagnosticLevel.INFO,
                    "voice",
                    "input.received",
                    **{field: "private-value"},
                )

        self.assertFalse(self.path.exists())

    def test_disabled_reporter_creates_no_file(self):
        reporter = StructuredDiagnosticReporter(self.path, enabled=False)

        self.assertTrue(reporter.emit(
            DiagnosticLevel.INFO,
            "application",
            "runtime.started",
        ))

        self.assertFalse(self.path.exists())

    def test_size_limit_rotates_to_one_previous_file(self):
        reporter = StructuredDiagnosticReporter(self.path, max_bytes=1_024)

        for count in range(20):
            reporter.emit(
                DiagnosticLevel.INFO,
                "application",
                "runtime.progress",
                count=count,
                status="bounded-metadata-only",
            )

        rotated = self.path.with_suffix(".jsonl.1")
        self.assertTrue(self.path.exists())
        self.assertTrue(rotated.exists())
        self.assertLessEqual(self.path.stat().st_size, 1_024)

    def test_write_failure_does_not_escape_into_application(self):
        blocked_parent = Path(self.temporary.name) / "not-a-directory"
        blocked_parent.write_text("occupied", encoding="utf-8")
        reporter = StructuredDiagnosticReporter(blocked_parent / "events.jsonl")

        written = reporter.emit(
            DiagnosticLevel.ERROR,
            "application",
            "runtime.failed",
            reason_code="test-boundary",
        )

        self.assertFalse(written)

    def test_invalid_event_names_and_non_scalar_values_are_rejected(self):
        reporter = StructuredDiagnosticReporter(self.path)

        with self.assertRaisesRegex(ValueError, "component"):
            reporter.emit(DiagnosticLevel.INFO, "Invalid Component", "event.ok")
        with self.assertRaisesRegex(TypeError, "scalar"):
            reporter.emit(
                DiagnosticLevel.INFO,
                "application",
                "event.ok",
                status=["not", "scalar"],
            )


if __name__ == "__main__":
    unittest.main()
