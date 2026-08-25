"""Capture one local German follow-up through Windows System.Speech."""

import base64
import math
import os
import subprocess
from collections.abc import Callable
from pathlib import Path

from application.voice_followup import FollowUpCaptureUnavailable


MIN_CAPTURE_TIMEOUT_SECONDS = 1.0
MAX_CAPTURE_TIMEOUT_SECONDS = 10.0
MAX_TRANSCRIPT_CHARACTERS = 240
POWERSHELL_GRACE_SECONDS = 3.0
DEFAULT_CULTURE = "de-DE"

_AVAILABILITY_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Speech
$recognizer = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() |
    Where-Object { $_.Culture.Name -eq '__CULTURE__' } |
    Select-Object -First 1
if ($null -eq $recognizer) { exit 2 }
Write-Output 'available'
"""

_CAPTURE_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Speech
$recognizer = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() |
    Where-Object { $_.Culture.Name -eq '__CULTURE__' } |
    Select-Object -First 1
if ($null -eq $recognizer) { exit 2 }
$engine = [System.Speech.Recognition.SpeechRecognitionEngine]::new($recognizer)
try {
    $choices = [System.Speech.Recognition.Choices]::new()
    $choices.Add([string[]]@('ja', 'ja bitte', 'bestätigen', 'ausführen', 'nein', 'abbrechen', 'stopp', 'nicht ausführen'))
    $builder = [System.Speech.Recognition.GrammarBuilder]::new($choices)
    $builder.Culture = $recognizer.Culture
    $engine.LoadGrammar([System.Speech.Recognition.Grammar]::new($builder))
    $engine.LoadGrammar([System.Speech.Recognition.DictationGrammar]::new())
    $engine.SetInputToDefaultAudioDevice()
    $result = $engine.Recognize([TimeSpan]::FromSeconds(__TIMEOUT__))
    if ($null -ne $result -and $result.Confidence -ge __CONFIDENCE__) {
        Write-Output $result.Text
    }
}
finally {
    $engine.Dispose()
}
"""


class WindowsSpeechFollowUpCapture:
    """Use the installed German Windows recognizer for one bounded answer."""

    def __init__(
        self,
        min_confidence: float = 0.35,
        culture: str = DEFAULT_CULTURE,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        powershell_path: str | Path | None = None,
    ):
        """Initialisiert den lokalen Erkenner mit festen sicheren Grenzen."""
        if not _valid_confidence(min_confidence):
            raise ValueError("Follow-up confidence must be between 0 and 1.")
        self.min_confidence = min_confidence
        self.culture = culture
        self.runner = runner
        self.powershell_path = Path(powershell_path or _default_powershell_path())
        self._available: bool | None = None

    def prepare(self) -> bool:
        """Prüft einmalig den deutschen Offline-Erkenner ohne Mikrofonzugriff."""
        if self._available is not None:
            return self._available
        result = self._run(_availability_script(self.culture), timeout=3.0)
        self._available = result is not None and result.stdout.strip() == "available"
        return self._available

    def capture(self, timeout: float) -> str | None:
        """Nimmt eine kurze lokale Antwort auf und gibt nur erkannten Text zurück."""
        if not _valid_timeout(timeout):
            raise ValueError("Follow-up timeout must be between 1 and 10 seconds.")
        script = _capture_script(self.culture, timeout, self.min_confidence)
        result = self._run(script, timeout=timeout + POWERSHELL_GRACE_SECONDS)
        if result is None:
            raise FollowUpCaptureUnavailable("Local follow-up capture is unavailable.")
        transcript = result.stdout.strip()
        return transcript[:MAX_TRANSCRIPT_CHARACTERS] or None

    def _run(
        self,
        script: str,
        timeout: float,
    ) -> subprocess.CompletedProcess[str] | None:
        """Startet eine verborgene feste PowerShell-Anweisung ohne Rohfehlerausgabe."""
        command = _powershell_command(self.powershell_path, script)
        try:
            result = self.runner(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return result if result.returncode == 0 else None


def _default_powershell_path() -> Path:
    """Ermittelt den festen Windows-PowerShell-Pfad ohne Shellsuche."""
    windows_root = Path(os.getenv("SystemRoot", r"C:\Windows"))
    return windows_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"


def _powershell_command(path: Path, script: str) -> list[str]:
    """Kodiert das feste Skript sicher für einen nicht interaktiven Prozess."""
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return [
        str(path),
        "-NoProfile",
        "-NonInteractive",
        "-WindowStyle",
        "Hidden",
        "-EncodedCommand",
        encoded,
    ]


def _availability_script(culture: str) -> str:
    """Setzt die begrenzte Sprachkultur in die feste Verfügbarkeitsprüfung ein."""
    return _AVAILABILITY_SCRIPT.replace("__CULTURE__", _safe_culture(culture))


def _capture_script(culture: str, timeout: float, confidence: float) -> str:
    """Setzt ausschließlich validierte Zahlen und Sprachkultur in das Skript ein."""
    script = _CAPTURE_SCRIPT.replace("__CULTURE__", _safe_culture(culture))
    script = script.replace("__TIMEOUT__", format(timeout, ".3f"))
    return script.replace("__CONFIDENCE__", format(confidence, ".3f"))


def _safe_culture(culture: str) -> str:
    """Erlaubt ausschließlich eine feste deutsche Windows-Sprachkultur."""
    if culture != DEFAULT_CULTURE:
        raise ValueError("Follow-up culture must be de-DE.")
    return culture


def _valid_timeout(value: float) -> bool:
    """Prüft eine endliche Aufnahmefrist gegen die Dialoggrenze."""
    return (
        isinstance(value, (int, float))
        and math.isfinite(value)
        and MIN_CAPTURE_TIMEOUT_SECONDS <= value <= MAX_CAPTURE_TIMEOUT_SECONDS
    )


def _valid_confidence(value: float) -> bool:
    """Prüft eine endliche Erkennungsschwelle gegen den Wertebereich."""
    return (
        isinstance(value, (int, float))
        and math.isfinite(value)
        and 0.0 <= value <= 1.0
    )
