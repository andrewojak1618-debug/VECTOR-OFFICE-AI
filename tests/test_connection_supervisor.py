"""State, recovery, and privacy tests for connection supervision."""

import json
import tempfile
import unittest
from pathlib import Path

from application.connection_supervisor import (
    CORE_PROVIDERS,
    ConnectionState,
    ConnectionSupervisor,
    ProviderHealth,
)
from diagnostics.events import StructuredDiagnosticReporter


class ConnectionSupervisorTests(unittest.TestCase):
    def test_failures_follow_bounded_schedule_and_cap_at_last_delay(self):
        supervisor = ConnectionSupervisor(retry_delays=(1.0, 2.0, 5.0))

        statuses = [supervisor.observe("wirepod", False) for _ in range(5)]

        self.assertEqual([1, 2, 5, 5, 5], [item.retry_after_seconds for item in statuses])
        self.assertEqual(5, statuses[-1].consecutive_failures)

    def test_recovery_resets_failures_and_reports_transition(self):
        supervisor = ConnectionSupervisor()
        supervisor.observe("vector-sdk", False)

        recovered = supervisor.observe("vector-sdk", True)

        self.assertEqual(ConnectionState.AVAILABLE, recovered.state)
        self.assertEqual(0, recovered.consecutive_failures)
        self.assertEqual(0, recovered.retry_after_seconds)
        self.assertTrue(recovered.changed)
        self.assertTrue(supervisor.consume_recovery("vector-sdk"))
        self.assertFalse(supervisor.consume_recovery("vector-sdk"))

    def test_initial_success_does_not_create_recovery_notice(self):
        supervisor = ConnectionSupervisor()

        supervisor.observe("wirepod", True)

        self.assertFalse(supervisor.consume_recovery("wirepod"))

    def test_bounded_wait_stops_after_success(self):
        results = iter((False, False, True))
        delays = []
        supervisor = ConnectionSupervisor(
            retry_delays=(1.0, 2.0, 5.0),
            sleeper=delays.append,
        )

        available = supervisor.wait_until_available(
            "ollama",
            lambda: next(results),
            max_attempts=3,
        )

        self.assertTrue(available)
        self.assertEqual([1.0, 2.0], delays)

    def test_health_check_failure_is_isolated_without_error_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "events.jsonl"
            supervisor = ConnectionSupervisor(StructuredDiagnosticReporter(path))

            available = supervisor.wait_until_available(
                "wirepod",
                lambda: (_ for _ in ()).throw(RuntimeError("private detail")),
                max_attempts=1,
            )
            encoded = path.read_text(encoding="utf-8")

        self.assertFalse(available)
        self.assertIn('"code":"provider.error"', encoded)
        self.assertIn('"error_code":"health-check-failed"', encoded)
        self.assertNotIn("private detail", encoded)

    def test_diagnostics_emit_only_state_changes_without_service_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "events.jsonl"
            reporter = StructuredDiagnosticReporter(path)
            supervisor = ConnectionSupervisor(reporter)
            supervisor.observe("openai", False)
            supervisor.observe("openai", False)
            supervisor.observe("openai", True)
            events = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(2, len(events))
        self.assertEqual(
            ["connection.unavailable", "connection.available"],
            [event["code"] for event in events],
        )
        encoded = json.dumps(events)
        self.assertNotIn("transcript", encoded)
        self.assertNotIn("prompt", encoded)

    def test_invalid_service_and_retry_configuration_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "service name"):
            ConnectionSupervisor().observe("Open AI", False)
        with self.assertRaisesRegex(ValueError, "ascending"):
            ConnectionSupervisor(retry_delays=(2.0, 1.0))
        with self.assertRaisesRegex(ValueError, "bounded"):
            ConnectionSupervisor(retry_delays=(1.0,)).wait_until_available(
                "openai",
                lambda: False,
                max_attempts=2,
            )

    def test_provider_overview_supports_all_safe_health_states(self):
        supervisor = ConnectionSupervisor()
        for provider in CORE_PROVIDERS:
            supervisor.register_provider(provider, enabled=False)

        self.assertEqual("disabled", supervisor.provider_overview()["openai"])
        unavailable = supervisor.observe_provider(
            "openai",
            ProviderHealth.UNAVAILABLE,
        )
        degraded = supervisor.observe_provider("openai", ProviderHealth.DEGRADED)
        healthy = supervisor.observe_provider("openai", ProviderHealth.HEALTHY)

        self.assertTrue(unavailable.changed)
        self.assertTrue(degraded.changed)
        self.assertTrue(healthy.changed)
        self.assertEqual("healthy", supervisor.provider_overview()["openai"])
        self.assertEqual(
            ProviderHealth.HEALTHY,
            supervisor.provider_status("openai").health,
        )

    def test_provider_overview_retains_last_state_without_duplicate_transition(self):
        supervisor = ConnectionSupervisor()
        supervisor.register_provider("ollama", enabled=True)

        first = supervisor.observe_provider("ollama", ProviderHealth.DEGRADED)
        repeated = supervisor.observe_provider("ollama", ProviderHealth.DEGRADED)

        self.assertTrue(first.changed)
        self.assertFalse(repeated.changed)
        self.assertEqual("degraded", supervisor.provider_overview()["ollama"])

    def test_registered_connection_updates_matching_provider_health(self):
        supervisor = ConnectionSupervisor()
        supervisor.register_provider("vector-sdk", enabled=True)

        supervisor.observe("vector-sdk", True)

        status = supervisor.provider_status("vector-sdk")
        self.assertEqual(ProviderHealth.HEALTHY, status.health)

    def test_provider_recovery_is_consumed_exactly_once(self):
        supervisor = ConnectionSupervisor()
        supervisor.register_provider("openai", enabled=True)
        supervisor.observe_provider("openai", ProviderHealth.UNAVAILABLE)
        supervisor.observe_provider("openai", ProviderHealth.HEALTHY)

        self.assertTrue(supervisor.consume_provider_recovery("openai"))
        self.assertFalse(supervisor.consume_provider_recovery("openai"))

        supervisor.observe_provider("openai", ProviderHealth.HEALTHY)
        self.assertFalse(supervisor.consume_provider_recovery("openai"))

    def test_initial_provider_success_is_not_reported_as_recovery(self):
        supervisor = ConnectionSupervisor()
        supervisor.register_provider("ollama", enabled=True)

        supervisor.observe_provider("ollama", ProviderHealth.HEALTHY)

        self.assertFalse(supervisor.consume_provider_recovery("ollama"))

    def test_provider_transitions_emit_only_fixed_content_free_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "events.jsonl"
            supervisor = ConnectionSupervisor(StructuredDiagnosticReporter(path))
            supervisor.register_provider("elevenlabs", enabled=False)
            supervisor.observe_provider("elevenlabs", ProviderHealth.UNAVAILABLE)
            supervisor.observe_provider("elevenlabs", ProviderHealth.DEGRADED)
            supervisor.observe_provider("elevenlabs", ProviderHealth.HEALTHY)
            events = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(
            [
                "provider.health.disabled",
                "provider.health.unavailable",
                "provider.health.degraded",
                "provider.recovered",
                "provider.health.healthy",
            ],
            [event["code"] for event in events],
        )
        self.assertEqual({"provider", "status"}, set(events[-1]["details"]))
        self.assertNotIn("api_key", json.dumps(events))

    def test_invalid_provider_state_is_rejected(self):
        with self.assertRaisesRegex(TypeError, "enabled flag"):
            ConnectionSupervisor().register_provider("openai", enabled=1)
        with self.assertRaisesRegex(TypeError, "Provider health"):
            ConnectionSupervisor().observe_provider("openai", "healthy")


if __name__ == "__main__":
    unittest.main()
