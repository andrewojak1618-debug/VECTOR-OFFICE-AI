"""Supervise local WirePod and Vector Office AI startup on Windows."""

import argparse
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

from application.connection_supervisor import ConnectionSupervisor
from application.process_control import (
    SingleInstanceLock,
    hidden_process_flags,
    process_exists,
    stop_process_tree,
    wirepod_process_running,
)
from config.settings import settings
from diagnostics.events import DiagnosticLevel, StructuredDiagnosticReporter


APP_RESTART_DELAYS = (2.0, 5.0, 10.0, 30.0)
WIREPOD_HEALTH_PATH = "/api/get_logs"


@dataclass(frozen=True)
class HostWatchdogConfig:
    """Define validated local paths and bounded recovery limits."""

    project_root: Path
    python_executable: Path
    application_entry: Path
    wirepod_host: str
    wirepod_executable: Path
    lock_path: Path
    poll_interval: float = 0.5
    startup_attempts: int = 5
    app_restart_attempts: int = 3
    owner_process_id: int | None = None

    def __post_init__(self) -> None:
        """Validiert Intervalle, Wiederholungsgrenzen und optionale Besitzer-ID."""
        if not 0.25 <= self.poll_interval <= 30.0:
            raise ValueError("Watchdog poll interval must be between 0.25 and 30.")
        if not 1 <= self.startup_attempts <= 6:
            raise ValueError("Watchdog startup attempts must be between 1 and 6.")
        if not 0 <= self.app_restart_attempts <= len(APP_RESTART_DELAYS):
            raise ValueError("Watchdog application restart attempts are invalid.")
        if self.owner_process_id is not None and self.owner_process_id <= 0:
            raise ValueError("Watchdog owner process ID must be positive.")


class WirePodHostService:
    """Check and start the configured local WirePod process safely."""

    def __init__(
        self,
        host: str,
        executable: Path,
        client: httpx.Client | None = None,
        process_running: Callable[[], bool] | None = None,
        process_launcher: Callable[..., object] | None = None,
    ):
        """Initialisiert die lokale WirePod-Prüfung mit austauschbaren Grenzen."""
        self.host = host.rstrip("/")
        self.executable = executable
        self.client = client or httpx.Client(timeout=1.5)
        self.process_running = process_running or wirepod_process_running
        self.process_launcher = process_launcher or subprocess.Popen

    def is_available(self) -> bool:
        """Prüft, ob WirePod aktuell am lokalen Log-Endpunkt antwortet."""
        try:
            response = self.client.get(f"{self.host}{WIREPOD_HEALTH_PATH}")
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    def ensure_started(self) -> bool:
        """Startet WirePod nur bei fehlendem Prozess und vorhandener Programmdatei."""
        if self.is_available() or self.process_running():
            return True
        if not self.executable.is_file():
            return False
        try:
            self.process_launcher(
                [str(self.executable), "-d"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=hidden_process_flags(),
            )
        except OSError:
            return False
        return True


class HostWatchdog:
    """Keep local startup dependencies healthy around one application process."""

    def __init__(
        self,
        config: HostWatchdogConfig,
        wirepod: WirePodHostService,
        diagnostics: StructuredDiagnosticReporter,
        process_launcher: Callable[..., object] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        instance_lock: SingleInstanceLock | None = None,
        owner_alive: Callable[[int], bool] | None = None,
        process_stopper: Callable[[object], None] | None = None,
    ):
        """Initialisiert die begrenzte Überwachung lokaler Dienste und Prozesse."""
        self.config = config
        self.wirepod = wirepod
        self.diagnostics = diagnostics
        self.process_launcher = process_launcher or subprocess.Popen
        self.sleeper = sleeper
        self.instance_lock = instance_lock or SingleInstanceLock(config.lock_path)
        self.owner_alive = owner_alive or process_exists
        self.process_stopper = process_stopper or stop_process_tree
        self.connections = ConnectionSupervisor(diagnostics, sleeper=sleeper)
        self._application_process = None

    def run(self) -> int:
        """Überwacht bis zum bewussten Anwendungsende oder begrenzten Fehler."""
        if not self.instance_lock.acquire():
            print("Vector Office AI startup is already active.")
            return 0
        self._emit(DiagnosticLevel.INFO, "watchdog.started", status="active")
        try:
            return self._run_locked()
        except KeyboardInterrupt:
            self._stop_application()
            return 0
        except Exception:
            self._stop_application()
            self._emit(
                DiagnosticLevel.ERROR,
                "watchdog.crashed",
                reason_code="unexpected-runtime-error",
            )
            return 1
        finally:
            self.instance_lock.release()

    def _run_locked(self) -> int:
        """Startet WirePod und Anwendung unter gehaltener Einzelinstanzsperre."""
        if not self._ensure_wirepod():
            self._emit(DiagnosticLevel.ERROR, "watchdog.blocked", status="wirepod")
            return 1
        self._application_process = self._start_application()
        if self._application_process is None:
            return 1
        return self._monitor_application()

    def _ensure_wirepod(self) -> bool:
        """Versucht WirePod mit begrenzten Wiederholungen verfügbar zu machen."""
        for attempt in range(1, self.config.startup_attempts + 1):
            available = self.wirepod.is_available()
            if not available:
                self.wirepod.ensure_started()
            status = self.connections.observe("wirepod", available)
            if available:
                return True
            if attempt < self.config.startup_attempts:
                self.sleeper(status.retry_after_seconds)
        return False

    def _monitor_application(self) -> int:
        """Überwacht Besitzer, Anwendung und WirePod bis zum definierten Ende."""
        failures = 0
        while True:
            if not self._owner_is_available():
                self._stop_application()
                self._emit(DiagnosticLevel.INFO, "watchdog.stopped", status="owner")
                return 0
            return_code = self._application_process.poll()
            if return_code is None:
                self._maintain_wirepod()
                self.sleeper(self.config.poll_interval)
                continue
            if return_code == 0:
                self._emit(DiagnosticLevel.INFO, "watchdog.stopped", status="requested")
                return 0
            if failures >= self.config.app_restart_attempts:
                self._emit(DiagnosticLevel.ERROR, "watchdog.exhausted", count=failures)
                return return_code
            failures += 1
            if not self._restart_application(failures):
                return 1

    def _maintain_wirepod(self) -> None:
        """Prüft WirePod während der Laufzeit und stößt bei Bedarf den Start an."""
        available = self.wirepod.is_available()
        self.connections.observe("wirepod", available)
        if not available:
            self.wirepod.ensure_started()

    def _restart_application(self, attempt: int) -> bool:
        """Startet die Anwendung nach fester Wartezeit kontrolliert neu."""
        delay = APP_RESTART_DELAYS[attempt - 1]
        self._emit(
            DiagnosticLevel.WARNING,
            "watchdog.restarting",
            attempt=attempt,
            retry_delay_seconds=delay,
        )
        self.sleeper(delay)
        if not self._ensure_wirepod():
            return False
        self._application_process = self._start_application()
        return self._application_process is not None

    def _start_application(self):
        """Startet die Anwendung verborgen und meldet nur strukturierte Metadaten."""
        try:
            process = self.process_launcher(
                [
                    str(self.config.python_executable),
                    str(self.config.application_entry),
                ],
                cwd=str(self.config.project_root),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=hidden_process_flags(),
            )
        except OSError:
            self._emit(DiagnosticLevel.ERROR, "watchdog.launch_failed")
            return None
        self._emit(DiagnosticLevel.INFO, "watchdog.application_started")
        return process

    def _stop_application(self) -> None:
        """Beendet ausschließlich den aktuell überwachten Anwendungsprozessbaum."""
        process = self._application_process
        if process is None or process.poll() is not None:
            return
        self.process_stopper(process)

    def _owner_is_available(self) -> bool:
        """Prüft, ob der optionale Besitzerprozess noch vorhanden ist."""
        owner_id = self.config.owner_process_id
        return owner_id is None or self.owner_alive(owner_id)

    def _emit(self, level: DiagnosticLevel, code: str, **details) -> None:
        """Schreibt ein begrenztes strukturiertes Watchdog-Ereignis."""
        self.diagnostics.emit(level, "host-watchdog", code, **details)


def _build_config(owner_process_id: int | None = None) -> HostWatchdogConfig:
    """Erzeugt die lokale Watchdog-Konfiguration aus geprüften Einstellungen."""
    project_root = Path(__file__).resolve().parent.parent
    return HostWatchdogConfig(
        project_root=project_root,
        python_executable=Path(sys.executable),
        application_entry=project_root / "main.py",
        wirepod_host=settings.WIREPOD_HOST,
        wirepod_executable=Path(settings.HOST_WATCHDOG_WIREPOD_EXECUTABLE),
        lock_path=project_root / "data" / "startup" / "host-watchdog.lock",
        poll_interval=settings.HOST_WATCHDOG_POLL_INTERVAL,
        startup_attempts=settings.HOST_WATCHDOG_STARTUP_ATTEMPTS,
        app_restart_attempts=settings.HOST_WATCHDOG_APP_RESTART_ATTEMPTS,
        owner_process_id=owner_process_id,
    )


def _parse_arguments():
    """Liest ausschließlich die optionale Besitzerprozess-ID ein."""
    parser = argparse.ArgumentParser(description="Run the local Vector watchdog.")
    parser.add_argument(
        "--parent-pid",
        type=int,
        default=None,
        help="Exit and stop the child application when this owner process ends.",
    )
    return parser.parse_args()


def main() -> None:
    """Startet den lokalen Watchdog und liefert dessen Beendigungsstatus."""
    if settings.INPUT_MODE.casefold().strip() != "wirepod":
        print("Managed Windows startup requires INPUT_MODE=wirepod.")
        raise SystemExit(2)
    config = _build_config(_parse_arguments().parent_pid)
    diagnostics = StructuredDiagnosticReporter(
        settings.DIAGNOSTICS_PATH,
        settings.DIAGNOSTICS_ENABLED,
        settings.DIAGNOSTICS_MAX_BYTES,
    )
    wirepod = WirePodHostService(config.wirepod_host, config.wirepod_executable)
    raise SystemExit(HostWatchdog(config, wirepod, diagnostics).run())


if __name__ == "__main__":
    main()
