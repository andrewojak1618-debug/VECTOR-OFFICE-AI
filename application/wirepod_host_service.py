"""Control the local WirePod host process and its passive SDK preflight."""

import subprocess
from collections.abc import Callable
from pathlib import Path

import httpx

from application.process_control import (
    hidden_process_flags,
    stop_wirepod_processes,
    wirepod_process_running,
    wirepod_process_started_at,
)
from application.wirepod_preflight import WirePodSdkProbe, WirePodSdkState


WIREPOD_HEALTH_PATH = "/api/get_logs"


class WirePodHostService:
    """Check, start, restart, and preflight the configured WirePod process."""

    def __init__(
        self,
        host: str,
        executable: Path,
        client: httpx.Client | None = None,
        process_running: Callable[[], bool] | None = None,
        process_launcher: Callable[..., object] | None = None,
        sdk_probe: WirePodSdkProbe | None = None,
        sdk_info_path: Path | None = None,
        process_started_at: Callable[[], float | None] | None = None,
        process_stopper: Callable[[], bool] | None = None,
    ):
        """Initialisiert lokale HTTP-, Prozess- und SDK-Prüfgrenzen."""
        self.host = host.rstrip("/")
        self.executable = executable
        self.client = client or httpx.Client(timeout=1.5)
        self.process_running = process_running or wirepod_process_running
        self.process_launcher = process_launcher or subprocess.Popen
        self.sdk_probe = sdk_probe
        self.sdk_info_path = sdk_info_path
        self.process_started_at = process_started_at or wirepod_process_started_at
        self.process_stopper = process_stopper or stop_wirepod_processes

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
        return self._launch()

    def sdk_state(self) -> WirePodSdkState:
        """Liefert den passiven SDK-Zustand oder überspringt alte Testgrenzen."""
        if self.sdk_probe is None:
            return WirePodSdkState.READY
        return self.sdk_probe.check()

    def credentials_changed_after_process_start(self) -> bool:
        """Prüft, ob WirePods SDK-Zuordnung nach dem Prozessstart geändert wurde."""
        if self.sdk_info_path is None or not self.executable.is_file():
            return False
        started_at = self.process_started_at()
        try:
            modified_at = self.sdk_info_path.stat().st_mtime
        except OSError:
            return False
        return started_at is not None and modified_at > started_at

    def restart(self) -> bool:
        """Startet ausschließlich den lokalen WirePod-Prozess kontrolliert neu."""
        if not self.process_stopper():
            return False
        return self._launch()

    def _launch(self) -> bool:
        """Startet genau einen verborgenen Chipper-Prozess aus festem Pfad."""
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
