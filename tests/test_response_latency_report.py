"""Tests für den inhaltsfreien lokalen Antwortlatenzbericht."""

import json
import tempfile
import unittest
from pathlib import Path

from diagnostics.response_latency_report import (
    collect_latest_latency,
    run_report,
)


class ResponseLatencyReportTests(unittest.TestCase):
    def test_report_shows_only_latest_fixed_latency_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            self._write_events(path)
            output = []

            available = run_report(path, output.append)

        text = "\n".join(output)
        self.assertTrue(available)
        self.assertIn("Antwort vorbereitet: 1200 ms", text)
        self.assertIn("TTS-Wiedergabe: 800 ms", text)
        self.assertIn("Gesamter Antwortturn: 2300 ms", text)
        self.assertNotIn("private Frage", text)
        self.assertNotIn("private Antwort", text)

    def test_invalid_or_foreign_events_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            payloads = (
                self._event("ollama", "response.finished", 9, "success"),
                self._event("response-latency", "unknown", 10, "success"),
                self._event("response-latency", "response.finished", -1, "success"),
            )
            self._write_payloads(path, payloads)

            latest = collect_latest_latency(path)

        self.assertEqual({}, latest)

    def test_missing_file_reports_no_measurements(self):
        with tempfile.TemporaryDirectory() as directory:
            output = []

            available = run_report(
                Path(directory) / "missing.jsonl",
                output.append,
            )

        self.assertFalse(available)
        self.assertIn("Noch keine", "\n".join(output))

    @classmethod
    def _write_events(cls, path: Path) -> None:
        """Schreibt feste Testereignisse einschließlich ungenutzter Privatfelder."""
        payloads = (
            cls._event("response-latency", "response.prepared", 1200, "success"),
            cls._event("response-latency", "response.tts.started", 1500, "active"),
            cls._event("response-latency", "response.tts.finished", 800, "success"),
            cls._event("response-latency", "response.finished", 2300, "success"),
        )
        payloads[0]["details"]["text"] = "private Frage"
        payloads[2]["details"]["answer"] = "private Antwort"
        cls._write_payloads(path, payloads)

    @staticmethod
    def _event(component: str, code: str, duration: int, status: str) -> dict:
        """Erzeugt eine kleine feste Ereignisstruktur für den Berichtstest."""
        return {
            "component": component,
            "code": code,
            "details": {"duration_ms": duration, "status": status},
        }

    @staticmethod
    def _write_payloads(path: Path, payloads: tuple[dict, ...]) -> None:
        """Speichert ausschließlich temporäre Testnutzdaten als JSONL."""
        path.write_text(
            "\n".join(json.dumps(item) for item in payloads),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
