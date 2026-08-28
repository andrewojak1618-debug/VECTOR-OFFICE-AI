"""Tests für inhaltsfreie Antwort- und TTS-Laufzeitereignisse."""

import json
import tempfile
import unittest
from pathlib import Path

from application.response_delivery import respond_and_speak
from brain.agent import Agent
from diagnostics.events import StructuredDiagnosticReporter
from diagnostics.response_latency import ResponseLatencyTrace


class ScriptedModel:
    """Liefert eine feste Antwort, ohne Testinhalte außerhalb des Turns zu halten."""

    def generate(self, _messages):
        """Gibt eine private Testantwort für die Datenschutzprüfung zurück."""
        return "Private Testantwort bleibt außerhalb der Diagnose."


class SuccessfulSpeech:
    """Bestätigt eine Wiedergabe, ohne Audio zu erzeugen."""

    def say(self, _text, _style=None):
        """Meldet eine erfolgreiche synthetische Sprachausgabe."""
        return True


class ResponseLatencyTests(unittest.TestCase):
    def test_trace_emits_only_fixed_phase_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            clock = iter((1.0, 1.4, 1.5, 2.1, 2.2)).__next__
            trace = ResponseLatencyTrace(
                StructuredDiagnosticReporter(path),
                clock,
            )

            trace.prepared()
            trace.speech_started()
            trace.speech_finished(True)
            trace.finish(True)
            events = self._events(path)

        self.assertEqual(
            [
                "response.started",
                "response.prepared",
                "response.tts.started",
                "response.tts.finished",
                "response.finished",
            ],
            [event["code"] for event in events],
        )
        self.assertEqual(400, events[1]["details"]["duration_ms"])
        self.assertEqual(500, events[2]["details"]["duration_ms"])
        self.assertEqual(600, events[3]["details"]["duration_ms"])
        self.assertEqual(1_200, events[4]["details"]["duration_ms"])
        self.assertEqual(
            {"duration_ms", "status"},
            set(events[4]["details"]),
        )

    def test_response_delivery_never_records_question_or_answer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            reporter = StructuredDiagnosticReporter(path)
            trace = ResponseLatencyTrace(reporter)

            completed = respond_and_speak(
                Agent(ScriptedModel()),
                SuccessfulSpeech(),
                "Private Frage darf nicht protokolliert werden.",
                trace,
            )
            serialized = path.read_text(encoding="utf-8")

        self.assertTrue(completed)
        self.assertNotIn("Private Frage", serialized)
        self.assertNotIn("Private Testantwort", serialized)
        self.assertIn('"code":"response.finished"', serialized)
        self.assertIn('"code":"response.tts.finished"', serialized)

    def test_failed_turn_finishes_once_without_tts_event(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            clock = iter((2.0, 2.2, 2.4)).__next__
            trace = ResponseLatencyTrace(
                StructuredDiagnosticReporter(path),
                clock,
            )

            trace.finish(False)
            trace.finish(True)
            events = self._events(path)

        self.assertEqual(2, len(events))
        self.assertEqual("failed", events[-1]["details"]["status"])
        self.assertNotIn("response.tts.started", str(events))

    @staticmethod
    def _events(path: Path) -> list[dict]:
        """Liest ausschließlich die temporären strukturierten Testereignisse."""
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
        ]


if __name__ == "__main__":
    unittest.main()
