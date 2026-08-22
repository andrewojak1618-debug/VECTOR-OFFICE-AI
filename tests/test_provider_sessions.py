"""Multi-turn tests for transparent OpenAI and local Ollama transitions."""

import json
import tempfile
import unittest
from pathlib import Path

from brain.agent import Agent
from brain.providers import FallbackProvider
from diagnostics.events import StructuredDiagnosticReporter


class ScriptedProvider:
    """Return deterministic responses or failures while recording safe batches."""

    def __init__(self, *outcomes):
        self.outcomes = iter(outcomes)
        self.received_batches = []

    def generate(self, messages):
        self.received_batches.append(tuple(messages))
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class MultiTurnProviderSessionTests(unittest.TestCase):
    def test_session_keeps_context_across_fallback_and_primary_recovery(self):
        primary = ScriptedProvider(
            "OpenAI beantwortet Runde eins.",
            RuntimeError("temporarily unavailable"),
            "OpenAI ist wieder verfügbar.",
        )
        fallback = ScriptedProvider("Ollama übernimmt Runde zwei.")
        with tempfile.TemporaryDirectory() as temp_dir:
            events_path = Path(temp_dir) / "events.jsonl"
            diagnostics = StructuredDiagnosticReporter(events_path)
            agent = Agent(FallbackProvider(primary, fallback, diagnostics))

            first = agent.respond("Merke dir den ersten Gesprächsschritt.")
            second = agent.respond("Welcher Provider antwortet jetzt?")
            third = agent.respond("Kann der Hauptanbieter wieder übernehmen?")

            events = self._read_events(events_path)

        self.assertIn("Runde eins", first)
        self.assertIn("Runde zwei", second)
        self.assertIn("wieder verfügbar", third)
        self.assertEqual(3, len(primary.received_batches))
        self.assertEqual(1, len(fallback.received_batches))
        final_context = tuple(
            message.content for message in primary.received_batches[-1][1:]
        )
        self.assertIn("Ollama übernimmt Runde zwei.", final_context)
        self.assertEqual(
            ["fallback.activated", "fallback.recovered"],
            [event["code"] for event in events],
        )

    def test_failed_turn_rolls_back_when_both_providers_are_unavailable(self):
        primary = ScriptedProvider(
            "Erste Antwort bleibt erhalten.",
            RuntimeError("primary unavailable"),
        )
        fallback = ScriptedProvider(RuntimeError("fallback unavailable"))
        agent = Agent(FallbackProvider(primary, fallback))
        agent.respond("Erste erfolgreiche Frage.")
        stable_history = agent.context.history

        with self.assertRaisesRegex(RuntimeError, "both failed"):
            agent.respond("Diese Frage bleibt unbeantwortet.")

        self.assertEqual(stable_history, agent.context.history)
        self.assertNotIn(
            "Diese Frage bleibt unbeantwortet.",
            tuple(message.content for message in agent.context.history),
        )

    @staticmethod
    def _read_events(path: Path) -> list[dict]:
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
        ]


if __name__ == "__main__":
    unittest.main()
