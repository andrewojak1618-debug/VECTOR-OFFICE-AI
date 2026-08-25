"""Supervise local WirePod and Vector Office AI startup on Windows."""

import argparse
import os
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from application.connection_supervisor import ConnectionSupervisor
from application.process_control import (
    SingleInstanceLock,
    hidden_process_flags,
    process_exists,
    stop_process_tree,
)
from application.wirepod_host_service import WirePodHostService
from application.wirepod_preflight import WirePodSdkProbe, WirePodSdkState
from config.settings import settings
from diagnostics.events import DiagnosticLevel, StructuredDiagnosticReporter


APP_RESTART_DELAYS = (2.0, 5.0, 10.0, 30.0)


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
        self._wirepod_sdk_restart_used = False

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
        if not self._prepare_wirepod():
            return 1
        self._application_process = self._start_application()
        if self._application_process is None:
            return 1
        return self._monitor_application()

    def _prepare_wirepod(self) -> bool:
        """Prüft WirePod-Prozess und SDK-Zugriff vor einem Anwendungsstart."""
        if not self._ensure_wirepod():
            self._emit(DiagnosticLevel.ERROR, "watchdog.blocked", status="wirepod")
            return False
        if self._ensure_wirepod_sdk():
            return True
        self._emit(DiagnosticLevel.ERROR, "watchdog.blocked", status="wirepod-sdk")
        return False

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

    def _ensure_wirepod_sdk(self) -> bool:
        """Validiert den SDK-Lesezugriff und repariert nur veraltete Zuordnungen."""
        state = self._sdk_state()
        self.connections.observe("wirepod-sdk", state is WirePodSdkState.READY)
        if state is WirePodSdkState.READY:
            return True
        if state is WirePodSdkState.AUTHENTICATION_FAILED:
            return self._repair_wirepod_sdk()
        if state in {WirePodSdkState.INVALID_RESPONSE, WirePodSdkState.DISABLED}:
            return False
        return self._wait_for_wirepod_sdk()

    def _repair_wirepod_sdk(self) -> bool:
        """Lädt eine nach Prozessstart geänderte WirePod-Zuordnung genau einmal neu."""
        if self._wirepod_sdk_restart_used:
            return False
        if not self._credentials_changed_after_start():
            return False
        self._wirepod_sdk_restart_used = True
        self._emit(DiagnosticLevel.WARNING, "watchdog.wirepod_sdk_restarting")
        if not self._restart_wirepod() or not self._ensure_wirepod():
            return False
        return self._wait_for_wirepod_sdk()

    def _wait_for_wirepod_sdk(self) -> bool:
        """Wiederholt den passiven SDK-Test nur innerhalb der Startgrenze."""
        terminal = {
            WirePodSdkState.AUTHENTICATION_FAILED,
            WirePodSdkState.INVALID_RESPONSE,
            WirePodSdkState.DISABLED,
        }
        for attempt in range(1, self.config.startup_attempts + 1):
            state = self._sdk_state()
            status = self.connections.observe(
                "wirepod-sdk",
                state is WirePodSdkState.READY,
            )
            if state is WirePodSdkState.READY:
                return True
            if state in terminal:
                return False
            if attempt < self.config.startup_attempts:
                self.sleeper(status.retry_after_seconds)
        return False

    def _sdk_state(self) -> WirePodSdkState:
        """Liest den SDK-Zustand über eine rückwärtskompatible Dienstgrenze."""
        checker = getattr(self.wirepod, "sdk_state", None)
        return checker() if checker is not None else WirePodSdkState.READY

    def _credentials_changed_after_start(self) -> bool:
        """Fragt ausschließlich den inhaltsfreien Zeitvergleich des Dienstes ab."""
        checker = getattr(
            self.wirepod,
            "credentials_changed_after_process_start",
            None,
        )
        return bool(checker()) if checker is not None else False

    def _restart_wirepod(self) -> bool:
        """Ruft die fest begrenzte lokale WirePod-Neustartgrenze auf."""
        restart = getattr(self.wirepod, "restart", None)
        return bool(restart()) if restart is not None else False

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
        if not self._prepare_wirepod():
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


def _wirepod_sdk_info_path() -> Path:
    """Erzeugt den festen lokalen Pfad zu WirePods SDK-Zuordnung."""
    roaming = os.getenv("APPDATA")
    base = Path(roaming) if roaming else Path.home() / "AppData" / "Roaming"
    return base / "wire-pod" / "jdocs" / "botSdkInfo.json"


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
    sdk_probe = WirePodSdkProbe(
        config.wirepod_host,
        settings.VECTOR_SERIAL,
        settings.WIREPOD_REQUEST_TIMEOUT,
    )
    wirepod = WirePodHostService(
        config.wirepod_host,
        config.wirepod_executable,
        sdk_probe=sdk_probe,
        sdk_info_path=_wirepod_sdk_info_path(),
    )
    raise SystemExit(HostWatchdog(config, wirepod, diagnostics).run())


if __name__ == "__main__":
    main()
