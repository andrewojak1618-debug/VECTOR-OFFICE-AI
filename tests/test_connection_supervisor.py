"""State, recovery, and privacy tests for connection supervision."""

import json
import tempfile
import unittest
from pathlib import Path

from application.connection_supervisor import (
    ConnectionState,
    ConnectionSupervisor,
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


if __name__ == "__main__":
    unittest.main()
