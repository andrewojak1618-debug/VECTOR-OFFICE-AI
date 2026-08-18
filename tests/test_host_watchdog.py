"""Local startup, restart, and privacy tests for the host watchdog."""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx

from application.host_watchdog import (
    HostWatchdog,
    HostWatchdogConfig,
    WirePodHostService,
    main,
)
from application.process_control import (
    SingleInstanceLock,
    process_exists,
    wirepod_process_running,
)
from diagnostics.events import DiagnosticLevel


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class FakeLock:
    def __init__(self, acquired=True):
        self.acquired = acquired
        self.released = False

    def acquire(self):
        return self.acquired

    def release(self):
        self.released = True


class FakeProcess:
    def __init__(self, poll_results):
        self.poll_results = list(poll_results)
        self.terminated = False
        self.pid = 12345

    def poll(self):
        if len(self.poll_results) > 1:
            return self.poll_results.pop(0)
        return self.poll_results[0]

    def terminate(self):
        self.terminated = True

    def wait(self, timeout):
        return 0

    def kill(self):
        self.terminated = True


class FakeWirePod:
    def __init__(self, availability):
        self.availability = list(availability)
        self.start_calls = 0

    def is_available(self):
        if len(self.availability) > 1:
            return self.availability.pop(0)
        return self.availability[0]

    def ensure_started(self):
        self.start_calls += 1
        return True


def make_config(root: Path, **overrides) -> HostWatchdogConfig:
    values = {
        "project_root": root,
        "python_executable": root / "python.exe",
        "application_entry": root / "main.py",
        "wirepod_host": "http://127.0.0.1:8080",
        "wirepod_executable": root / "chipper.exe",
        "lock_path": root / "data" / "startup" / "watchdog.lock",
        "poll_interval": 0.25,
        "startup_attempts": 3,
        "app_restart_attempts": 2,
    }
    values.update(overrides)
    return HostWatchdogConfig(**values)


class HostWatchdogTests(unittest.TestCase):
    def test_native_process_check_finds_current_process(self):
        self.assertTrue(process_exists(os.getpid()))
        self.assertFalse(process_exists(2_000_000_000))

    @patch("application.process_control.subprocess.run")
    def test_wirepod_process_check_is_independent_of_tasklist_encoding(self, run):
        run.return_value = SimpleNamespace(stdout=b"\x81 chipper.exe\r\n")

        self.assertTrue(wirepod_process_running())
        self.assertNotIn("text", run.call_args.kwargs)

    @patch("application.host_watchdog.settings.INPUT_MODE", "console")
    def test_managed_startup_rejects_hidden_console_mode(self):
        with self.assertRaises(SystemExit) as context:
            main()

        self.assertEqual(2, context.exception.code)

    def test_config_rejects_unbounded_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                make_config(root, poll_interval=0.1)
            make_config(root, startup_attempts=6)
            with self.assertRaises(ValueError):
                make_config(root, startup_attempts=7)
            with self.assertRaises(ValueError):
                make_config(root, app_restart_attempts=5)

    def test_single_instance_lock_blocks_a_second_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "watchdog.lock"
            first = SingleInstanceLock(path)
            second = SingleInstanceLock(path)
            self.assertTrue(first.acquire())
            try:
                self.assertFalse(second.acquire())
            finally:
                first.release()
                second.release()

    def test_wirepod_starts_only_when_endpoint_and_process_are_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "chipper.exe"
            executable.touch()
            client = MagicMock()
            client.get.side_effect = httpx.ConnectError("offline")
            launcher = MagicMock()
            service = WirePodHostService(
                "http://127.0.0.1:8080",
                executable,
                client=client,
                process_running=lambda: False,
                process_launcher=launcher,
            )

            self.assertTrue(service.ensure_started())
            self.assertEqual([str(executable), "-d"], launcher.call_args.args[0])

    def test_wirepod_does_not_duplicate_a_running_process(self):
        client = MagicMock()
        client.get.side_effect = httpx.ConnectError("offline")
        launcher = MagicMock()
        service = WirePodHostService(
            "http://127.0.0.1:8080",
            Path("missing.exe"),
            client=client,
            process_running=lambda: True,
            process_launcher=launcher,
        )

        self.assertTrue(service.ensure_started())
        launcher.assert_not_called()

    def test_watchdog_waits_for_wirepod_before_starting_application(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wirepod = FakeWirePod([False, True])
            launcher = MagicMock(return_value=FakeProcess([0]))
            sleeper = MagicMock()
            lock = FakeLock()
            watchdog = HostWatchdog(
                make_config(root),
                wirepod,
                MagicMock(),
                process_launcher=launcher,
                sleeper=sleeper,
                instance_lock=lock,
            )

            self.assertEqual(0, watchdog.run())
            self.assertEqual(1, wirepod.start_calls)
            sleeper.assert_called_once_with(1.0)
            self.assertTrue(lock.released)

    def test_slow_cold_start_accepts_the_sixth_wirepod_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wirepod = FakeWirePod([False, False, False, False, False, True])
            sleeper = MagicMock()
            watchdog = HostWatchdog(
                make_config(root, startup_attempts=6),
                wirepod,
                MagicMock(),
                process_launcher=MagicMock(return_value=FakeProcess([0])),
                sleeper=sleeper,
                instance_lock=FakeLock(),
            )

            self.assertEqual(0, watchdog.run())
            self.assertEqual(5, wirepod.start_calls)
            self.assertEqual(
                [1.0, 2.0, 5.0, 10.0, 30.0],
                [call.args[0] for call in sleeper.call_args_list],
            )

    def test_failed_application_restarts_with_bounded_delay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            launcher = MagicMock(side_effect=[FakeProcess([1]), FakeProcess([0])])
            sleeper = MagicMock()
            watchdog = HostWatchdog(
                make_config(root),
                FakeWirePod([True]),
                MagicMock(),
                process_launcher=launcher,
                sleeper=sleeper,
                instance_lock=FakeLock(),
            )

            self.assertEqual(0, watchdog.run())
            self.assertEqual(2, launcher.call_count)
            sleeper.assert_called_once_with(2.0)

    def test_deliberate_application_exit_is_not_restarted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            launcher = MagicMock(return_value=FakeProcess([0]))
            watchdog = HostWatchdog(
                make_config(root),
                FakeWirePod([True]),
                MagicMock(),
                process_launcher=launcher,
                sleeper=MagicMock(),
                instance_lock=FakeLock(),
            )

            self.assertEqual(0, watchdog.run())
            self.assertEqual(1, launcher.call_count)

    def test_running_application_triggers_wirepod_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wirepod = FakeWirePod([True, False])
            watchdog = HostWatchdog(
                make_config(root),
                wirepod,
                MagicMock(),
                process_launcher=MagicMock(return_value=FakeProcess([None, 0])),
                sleeper=MagicMock(),
                instance_lock=FakeLock(),
            )

            self.assertEqual(0, watchdog.run())
            self.assertEqual(1, wirepod.start_calls)

    def test_inactive_lock_prevents_all_process_launches(self):
        with tempfile.TemporaryDirectory() as directory:
            launcher = MagicMock()
            watchdog = HostWatchdog(
                make_config(Path(directory)),
                FakeWirePod([True]),
                MagicMock(),
                process_launcher=launcher,
                instance_lock=FakeLock(acquired=False),
            )

            self.assertEqual(0, watchdog.run())
            launcher.assert_not_called()

    def test_unexpected_runtime_error_is_sanitized_and_releases_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = FakeLock()
            diagnostics = MagicMock()
            wirepod = FakeWirePod([True])
            wirepod.is_available = MagicMock(side_effect=RuntimeError("private"))
            watchdog = HostWatchdog(
                make_config(Path(directory)),
                wirepod,
                diagnostics,
                instance_lock=lock,
            )

            self.assertEqual(1, watchdog.run())
            self.assertTrue(lock.released)
            diagnostics.emit.assert_any_call(
                DiagnosticLevel.ERROR,
                "host-watchdog",
                "watchdog.crashed",
                reason_code="unexpected-runtime-error",
            )

    def test_missing_task_owner_stops_the_application_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            process = FakeProcess([None])
            stopper = MagicMock()
            watchdog = HostWatchdog(
                make_config(root, owner_process_id=123),
                FakeWirePod([True]),
                MagicMock(),
                process_launcher=MagicMock(return_value=process),
                sleeper=MagicMock(),
                instance_lock=FakeLock(),
                owner_alive=lambda process_id: False,
                process_stopper=stopper,
            )

            self.assertEqual(0, watchdog.run())
            stopper.assert_called_once_with(process)

    def test_startup_scripts_do_not_contain_secrets(self):
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for pattern in ("*.ps1", "*.vbs")
            for path in (PROJECT_ROOT / "scripts").glob(pattern)
        ).casefold()

        self.assertNotIn("openai_api_key", combined)
        self.assertNotIn("vector_serial", combined)
        self.assertNotIn(".env", combined)

    def test_scheduled_task_is_delayed_and_single_instance(self):
        installer = (
            PROJECT_ROOT / "scripts" / "install_windows_startup.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn("-AtLogOn", installer)
        self.assertIn("DelaySeconds = 20", installer)
        self.assertIn("-MultipleInstances IgnoreNew", installer)
        self.assertIn("-RunLevel Limited", installer)
        self.assertIn("wscript.exe", installer)
        self.assertIn("start_vector_office_hidden.vbs", installer)
        self.assertIn("-Hidden", installer)
        self.assertIn("SupportsShouldProcess = $true", installer)

    def test_windowless_launcher_runs_only_the_fixed_start_script(self):
        launcher = (
            PROJECT_ROOT / "scripts" / "start_vector_office_hidden.vbs"
        ).read_text(encoding="utf-8")
        start_script = (
            PROJECT_ROOT / "scripts" / "start_vector_office.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn("start_vector_office.ps1", launcher)
        self.assertIn("shell.Run(command, 0, True)", launcher)
        self.assertIn("-NonInteractive", launcher)
        self.assertIn("-WindowStyle Hidden", launcher)
        self.assertNotIn("WScript.Arguments", launcher)
        self.assertIn("ParentProcessId", start_script)
        self.assertIn("--parent-pid $ownerProcessId", start_script)
        self.assertNotIn("--parent-pid $PID", start_script)

    def test_startup_acceptance_checks_task_services_and_duplicates(self):
        diagnostic = (
            PROJECT_ROOT / "scripts" / "check_windows_startup.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn("Get-ScheduledTask -TaskName", diagnostic)
        self.assertIn("Get-ScheduledTaskInfo -TaskName", diagnostic)
        self.assertIn("/api/get_logs", diagnostic)
        self.assertIn("/api/tags", diagnostic)
        self.assertIn("-m application.host_watchdog", diagnostic)
        self.assertIn("ParentProcessId -notin", diagnostic)
        self.assertIn("No duplicate WirePod process", diagnostic)
        self.assertIn("No secrets or conversation data were read", diagnostic)


if __name__ == "__main__":
    unittest.main()
