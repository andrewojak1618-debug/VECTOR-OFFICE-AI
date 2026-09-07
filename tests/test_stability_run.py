"""Tests für den inhaltsfreien begrenzten lokalen Stabilitätslauf."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from application.connection_supervisor import ProviderHealth
from diagnostics.provider_status import ProviderDiagnosticResult
from diagnostics.stability_run import (
    LOCAL_PROVIDERS,
    print_report,
    run_stability_check,
    write_report,
)


def provider_results(**states: ProviderHealth):
    """Erzeugt feste Diagnoseergebnisse ohne echte Providerzugriffe."""
    return tuple(
        ProviderDiagnosticResult(provider, states[provider], "verworfen")
        for provider in sorted(LOCAL_PROVIDERS)
    )


class StabilityRunTests(unittest.TestCase):
    def test_healthy_run_passes_without_sleep_after_last_sample(self):
        sleeper = MagicMock()
        collector = MagicMock(
            return_value=provider_results(
                ollama=ProviderHealth.HEALTHY,
                wirepod=ProviderHealth.HEALTHY,
                **{"vector-sdk": ProviderHealth.HEALTHY},
            )
        )
        clock = MagicMock(side_effect=(10.0, 12.0))

        report = run_stability_check(3, 5.0, collector, sleeper, clock)

        self.assertTrue(report.passed)
        self.assertEqual(2_000, report.duration_ms)
        self.assertEqual(3, collector.call_count)
        self.assertEqual([5.0, 5.0], [call.args[0] for call in sleeper.call_args_list])

    def test_transitions_and_longest_outage_are_aggregated(self):
        states = iter(
            (
                ProviderHealth.HEALTHY,
                ProviderHealth.UNAVAILABLE,
                ProviderHealth.UNAVAILABLE,
                ProviderHealth.HEALTHY,
            )
        )

        def collect():
            """Liefert eine kontrollierte Vector-Zustandsfolge."""
            vector = next(states)
            return provider_results(
                ollama=ProviderHealth.HEALTHY,
                wirepod=ProviderHealth.HEALTHY,
                **{"vector-sdk": vector},
            )

        report = run_stability_check(
            4,
            1.0,
            collect,
            sleeper=lambda _seconds: None,
            clock=MagicMock(side_effect=(0.0, 3.0)),
        )
        vector = next(item for item in report.providers if item.provider == "vector-sdk")

        self.assertFalse(report.passed)
        self.assertEqual(2, vector.healthy_samples)
        self.assertEqual(2, vector.unavailable_samples)
        self.assertEqual(2, vector.transitions)
        self.assertEqual(2, vector.longest_unavailable_streak)

    def test_missing_or_failed_collection_marks_all_local_providers_unavailable(self):
        for collector in (lambda: (), lambda: (_ for _ in ()).throw(RuntimeError("secret"))):
            with self.subTest(collector=collector):
                report = run_stability_check(
                    1,
                    1.0,
                    collector,
                    clock=MagicMock(side_effect=(0.0, 0.1)),
                )

                self.assertFalse(report.passed)
                self.assertTrue(
                    all(item.unavailable_samples == 1 for item in report.providers)
                )

    def test_schedule_rejects_unbounded_values(self):
        invalid = ((0, 1.0), (121, 1.0), (2, 0.5), (120, 60.0))

        for sample_count, interval in invalid:
            with self.subTest(values=(sample_count, interval)):
                with self.assertRaisesRegex(ValueError, "safe range"):
                    run_stability_check(sample_count, interval)

    def test_report_contains_only_fixed_aggregates(self):
        report = run_stability_check(
            1,
            1.0,
            lambda: provider_results(
                ollama=ProviderHealth.HEALTHY,
                wirepod=ProviderHealth.HEALTHY,
                **{"vector-sdk": ProviderHealth.HEALTHY},
            ),
            clock=MagicMock(side_effect=(0.0, 0.1)),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_report(report, Path(temp_dir) / "stability.json")
            encoded = path.read_text(encoding="utf-8")
            payload = json.loads(encoded)

        self.assertTrue(payload["passed"])
        self.assertEqual(1, payload["sample_count"])
        self.assertEqual(set(LOCAL_PROVIDERS), set(payload["providers"]))
        for forbidden in ("secret", "prompt", "answer", "document", "endpoint"):
            self.assertNotIn(forbidden, encoded.casefold())

    def test_terminal_report_uses_only_counts(self):
        report = run_stability_check(
            1,
            1.0,
            lambda: provider_results(
                ollama=ProviderHealth.HEALTHY,
                wirepod=ProviderHealth.HEALTHY,
                **{"vector-sdk": ProviderHealth.HEALTHY},
            ),
            clock=MagicMock(side_effect=(0.0, 0.1)),
        )
        lines = []

        print_report(report, lines.append)

        output = "\n".join(lines)
        self.assertIn("Gesamtergebnis: bestanden", output)
        self.assertIn("verfügbar 1", output)
        self.assertNotIn("verworfen", output)


if __name__ == "__main__":
    unittest.main()
