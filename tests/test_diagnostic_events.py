"""Privacy and retention tests for structured local runtime diagnostics."""

import json
import tempfile
import unittest
from pathlib import Path

from diagnostics.events import (
    DiagnosticLevel,
    ProviderErrorCode,
    ProviderEvent,
    ProviderOperation,
    StructuredDiagnosticReporter,
    emit_provider_event,
)


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

        for field in (
            "transcript",
            "prompt",
            "response",
            "api_key",
            "document",
            "memory",
            "embedding",
        ):
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

    def test_provider_lifecycle_uses_only_fixed_safe_metadata(self):
        reporter = StructuredDiagnosticReporter(self.path)
        clock = iter((10.0, 10.125)).__next__

        operation = ProviderOperation(reporter, "ollama", clock=clock)
        operation.finished()
        emit_provider_event(
            reporter,
            ProviderEvent.FALLBACK,
            "openai",
            fallback="ollama",
            error_code=ProviderErrorCode.PRIMARY_UNAVAILABLE,
        )
        emit_provider_event(
            reporter,
            ProviderEvent.RECOVERED,
            "openai",
            fallback="ollama",
        )
        events = self._read_events()

        self.assertEqual(
            ["provider.started", "provider.finished", "provider.fallback", "provider.recovered"],
            [event["code"] for event in events],
        )
        self.assertEqual(125, events[1]["details"]["duration_ms"])
        self.assertEqual(
            {"provider", "duration_ms"},
            set(events[1]["details"]),
        )

    def test_provider_failures_use_safe_codes_without_message_content(self):
        reporter = StructuredDiagnosticReporter(self.path)
        timeout_clock = iter((1.0, 1.2)).__next__
        error_clock = iter((2.0, 2.05)).__next__

        ProviderOperation(reporter, "openai", timeout_clock).timeout()
        ProviderOperation(reporter, "elevenlabs", error_clock).error(
            ProviderErrorCode.PROVIDER_UNAVAILABLE
        )
        events = self._read_events()
        encoded = json.dumps(events)

        self.assertEqual("provider.timeout", events[1]["code"])
        self.assertEqual("request-timeout", events[1]["details"]["error_code"])
        self.assertEqual("provider.error", events[3]["code"])
        self.assertEqual(
            "provider-unavailable",
            events[3]["details"]["error_code"],
        )
        for private_value in ("private question", "private answer", "secret-key"):
            self.assertNotIn(private_value, encoded)

    def test_provider_interface_rejects_free_form_event_and_error_values(self):
        reporter = StructuredDiagnosticReporter(self.path)

        with self.assertRaisesRegex(TypeError, "Provider event"):
            emit_provider_event(reporter, "provider.error", "ollama")
        with self.assertRaisesRegex(TypeError, "error code"):
            emit_provider_event(
                reporter,
                ProviderEvent.ERROR,
                "ollama",
                error_code="private failure detail",
            )
        with self.assertRaisesRegex(ValueError, "duration"):
            emit_provider_event(
                reporter,
                ProviderEvent.FINISHED,
                "ollama",
                duration_ms=-1,
            )

        with self.assertRaisesRegex(ValueError, "error code"):
            reporter.emit(
                DiagnosticLevel.ERROR,
                "ollama",
                "provider.error",
                provider="ollama",
                error_code="private failure detail",
            )

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

    def _read_events(self):
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
        ]


if __name__ == "__main__":
    unittest.main()
