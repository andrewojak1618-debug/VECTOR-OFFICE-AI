"""Local Ollama service discovery and lifecycle management."""

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

import httpx


DEFAULT_MODEL_KEEP_ALIVE = "30m"


class OllamaRuntime:
    """Ensure that the configured local Ollama service is reachable."""

    def __init__(
        self,
        base_url: str,
        executable: str = "",
        startup_timeout: float = 15.0,
        poll_interval: float = 0.5,
        client: httpx.Client | None = None,
        process_launcher: Callable[..., object] | None = None,
    ):
        """Initialisiert Erreichbarkeitsprüfung und begrenzte lokale Startparameter."""
        self.base_url = base_url.rstrip("/")
        self.executable = executable.strip()
        self.startup_timeout = startup_timeout
        self.poll_interval = poll_interval
        self.client = client or httpx.Client(timeout=1.5)
        self.process_launcher = process_launcher or subprocess.Popen

    def ensure_available(self) -> bool:
        """Meldet Ollamas Verfügbarkeit und startet den Dienst bei Bedarf."""
        if self.is_available():
            print("Ollama is online. [OK]")
            return True
        executable = self._resolve_executable()
        if executable is None:
            print("Ollama executable was not found. [WARNING]")
            return False
        print(f"Starting local Ollama: {executable}")
        if not self._start_service(executable):
            return False
        return self._wait_until_ready()

    def preload_model(
        self,
        model_name: str,
        timeout: float,
        keep_alive: str = DEFAULT_MODEL_KEEP_ALIVE,
    ) -> bool:
        """Lädt ein lokales Modell über eine leere, inhaltsfreie Anfrage vor."""
        normalized_name = model_name.strip()
        if not normalized_name or timeout <= 0:
            raise ValueError("Ollama preload settings are invalid.")
        payload = {
            "model": normalized_name,
            "stream": False,
            "keep_alive": keep_alive,
        }
        try:
            response = self.client.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            print("Ollama model preload failed. [WARNING]")
            return False
        print("Ollama model is preloaded. [OK]")
        return True

    def _start_service(self, executable: Path) -> bool:
        """Startet ausschließlich die aufgelöste lokale Ollama-Programmdatei."""
        try:
            self.process_launcher(
                [str(executable), "serve"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=self._creation_flags(),
            )
        except OSError as exc:
            print(f"Ollama could not be started: {exc}")
            return False
        return True

    def _wait_until_ready(self) -> bool:
        """Wartet innerhalb einer festen Frist auf den lokalen Ollama-Dienst."""
        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            time.sleep(self.poll_interval)
            if self.is_available():
                print("Ollama started successfully. [OK]")
                return True
        print("Ollama did not become ready in time. [WARNING]")
        return False

    def is_available(self) -> bool:
        """Prüft den lokalen Versionsendpunkt ohne Transportdetails offenzulegen."""
        try:
            response = self.client.get(f"{self.base_url}/api/version")
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    def _resolve_executable(self) -> Path | None:
        """Löst nur konfigurierte oder bekannte lokale Ollama-Pfade auf."""
        if self.executable:
            configured_path = Path(self.executable).expanduser()

            if configured_path.is_file():
                return configured_path

            return None

        path_executable = shutil.which("ollama")

        if path_executable:
            return Path(path_executable)

        local_app_data = os.getenv("LOCALAPPDATA")

        if not local_app_data:
            return None

        candidates = (
            Path(local_app_data) / "Programs" / "Ollama" / "ollama.exe",
            Path(local_app_data) / "Programs" / "OllamaArm64" / "ollama.exe",
        )

        return next((path for path in candidates if path.is_file()), None)

    @staticmethod
    def _creation_flags() -> int:
        """Liefert Windows-Flags für einen unsichtbaren, abgetrennten Dienst."""
        if os.name != "nt":
            return 0

        return (
            getattr(subprocess, "CREATE_NO_WINDOW", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
        )
