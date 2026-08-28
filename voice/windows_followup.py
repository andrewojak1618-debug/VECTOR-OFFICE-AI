"""Capture one local German follow-up through a warmed Windows recognizer."""

import base64
import math
import os
import queue
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

from application.voice_followup import FollowUpCaptureUnavailable


MIN_CAPTURE_TIMEOUT_SECONDS = 1.0
MAX_CAPTURE_TIMEOUT_SECONDS = 10.0
MAX_TRANSCRIPT_CHARACTERS = 240
STARTUP_TIMEOUT_SECONDS = 8.0
RESPONSE_GRACE_SECONDS = 2.0
DEFAULT_CULTURE = "de-DE"
_END_OF_OUTPUT = object()

_SERVER_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Speech
$recognizer = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() |
    Where-Object { $_.Culture.Name -eq '__CULTURE__' } |
    Select-Object -First 1
if ($null -eq $recognizer) { exit 2 }
$engine = [System.Speech.Recognition.SpeechRecognitionEngine]::new($recognizer)
try {
    $choices = [System.Speech.Recognition.Choices]::new()
    $choices.Add([string[]]@(
        'ja', 'ja bitte', 'ja bitte öffnen', 'ja bitte ausführen',
        'ja den ordner bitte öffnen', 'ja die datei bitte öffnen',
        'bestätigen', 'bitte bestätigen', 'ausführen',
        'nein', 'nein danke', 'abbrechen', 'stopp', 'nicht ausführen'
    ))
    $builder = [System.Speech.Recognition.GrammarBuilder]::new($choices)
    $builder.Culture = $recognizer.Culture
    $confirmationGrammar = [System.Speech.Recognition.Grammar]::new($builder)
    $conversationChoices = [System.Speech.Recognition.Choices]::new()
    $conversationChoices.Add([string[]]@(
        'danke', 'danke dir', 'dankeschön', 'vielen dank',
        'das reicht', 'stopp'
    ))
    $conversationBuilder = [System.Speech.Recognition.GrammarBuilder]::new(
        $conversationChoices
    )
    $conversationBuilder.Culture = $recognizer.Culture
    $conversationControlGrammar = [System.Speech.Recognition.Grammar]::new(
        $conversationBuilder
    )
    $conversationControlGrammar.Priority = 127
    [Console]::Out.WriteLine('READY')
    [Console]::Out.Flush()
    while ($true) {
        $command = [Console]::In.ReadLine()
        if ($null -eq $command -or $command -eq 'STOP') { break }
        if ($command -notmatch '^CAPTURE (CONFIRMATION|CONVERSATION) ([1-9][0-9]{2,4})$') { continue }
        $mode = $Matches[1]
        $milliseconds = [int]$Matches[2]
        if ($milliseconds -lt 1000 -or $milliseconds -gt 10000) { continue }
        try {
            $engine.UnloadAllGrammars()
            if ($mode -eq 'CONVERSATION') {
                $engine.LoadGrammar($conversationControlGrammar)
                $engine.LoadGrammar([System.Speech.Recognition.DictationGrammar]::new())
            }
            else {
                $engine.LoadGrammar($confirmationGrammar)
            }
            $engine.SetInputToDefaultAudioDevice()
            [Console]::Out.WriteLine('LISTENING')
            [Console]::Out.Flush()
            $result = $engine.Recognize([TimeSpan]::FromMilliseconds($milliseconds))
            $engine.SetInputToNull()
            $text = ''
            if ($null -ne $result -and $result.Confidence -ge __CONFIDENCE__) {
                $text = [Convert]::ToBase64String(
                    [System.Text.Encoding]::UTF8.GetBytes($result.Text)
                )
            }
            [Console]::Out.WriteLine('RESULT:' + $text)
            [Console]::Out.Flush()
        }
        catch {
            try { $engine.SetInputToNull() } catch {}
            [Console]::Out.WriteLine('ERROR')
            [Console]::Out.Flush()
        }
    }
}
finally {
    $engine.Dispose()
}
"""


class WindowsSpeechFollowUpCapture:
    """Hält den deutschen Windows-Erkenner für eine kurze Antwort bereit."""

    def __init__(
        self,
        min_confidence: float = 0.15,
        culture: str = DEFAULT_CULTURE,
        process_factory: Callable[..., subprocess.Popen[str]] = subprocess.Popen,
        powershell_path: str | Path | None = None,
    ):
        """Initialisiert den lokalen Erkenner mit festen sicheren Grenzen."""
        if not _valid_confidence(min_confidence):
            raise ValueError("Follow-up confidence must be between 0 and 1.")
        self.min_confidence = min_confidence
        self.culture = culture
        self.process_factory = process_factory
        self.powershell_path = Path(powershell_path or _default_powershell_path())
        self._process: subprocess.Popen[str] | None = None
        self._responses: queue.Queue[str | object] = queue.Queue()
        self._reader: threading.Thread | None = None

    def prepare(self) -> bool:
        """Startet und erwärmt den Offline-Erkenner höchstens einmal gleichzeitig."""
        _safe_culture(self.culture)
        if self._process is not None and self._process.poll() is None:
            return True
        self.close()
        if not self._start_process():
            return False
        if self._next_response(STARTUP_TIMEOUT_SECONDS) == "READY":
            return True
        self.close()
        return False

    def capture(self, timeout: float, free_text: bool = False) -> str | None:
        """Erfasst unmittelbar eine kurze Antwort über den vorgewärmten Erkenner."""
        if not _valid_timeout(timeout):
            raise ValueError("Follow-up timeout must be between 1 and 10 seconds.")
        if not isinstance(free_text, bool):
            raise TypeError("Follow-up mode must be a boolean.")
        command = _capture_command(timeout, free_text)
        if not self.prepare() or not self._write_command(command):
            raise _unavailable()
        if self._next_response(RESPONSE_GRACE_SECONDS) != "LISTENING":
            self.close()
            raise _unavailable()
        response = self._next_response(timeout + RESPONSE_GRACE_SECONDS)
        if not isinstance(response, str) or not response.startswith("RESULT:"):
            self.close()
            raise _unavailable()
        return _decode_transcript(response.removeprefix("RESULT:"))

    def close(self) -> None:
        """Beendet den lokalen Erkenner und gibt das Mikrofon sicher frei."""
        process = self._process
        self._process = None
        if process is None:
            return
        _request_process_stop(process)
        self._responses = queue.Queue()
        self._reader = None

    def _start_process(self) -> bool:
        """Startet den festen verborgenen PowerShell-Server ohne Shellzugriff."""
        command = _powershell_command(
            self.powershell_path,
            _server_script(self.culture, self.min_confidence),
        )
        try:
            process = self.process_factory(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError:
            return False
        if process.stdin is None or process.stdout is None:
            _request_process_stop(process)
            return False
        self._process = process
        self._responses = queue.Queue()
        self._reader = threading.Thread(
            target=self._read_process_output,
            args=(process,),
            daemon=True,
        )
        self._reader.start()
        return True

    def _read_process_output(self, process: subprocess.Popen[str]) -> None:
        """Überträgt feste Protokollzeilen aus dem lokalen Unterprozess."""
        if process.stdout is None:
            self._responses.put(_END_OF_OUTPUT)
            return
        try:
            for line in process.stdout:
                self._responses.put(line.rstrip("\r\n"))
        finally:
            self._responses.put(_END_OF_OUTPUT)

    def _next_response(self, timeout: float) -> str | object | None:
        """Liest genau eine begrenzte Protokollantwort ohne Rohfehler."""
        try:
            return self._responses.get(timeout=timeout)
        except queue.Empty:
            return None

    def _write_command(self, command: str) -> bool:
        """Sendet ausschließlich einen intern erzeugten begrenzten Steuerbefehl."""
        process = self._process
        if process is None or process.stdin is None or process.poll() is not None:
            return False
        try:
            process.stdin.write(command + "\n")
            process.stdin.flush()
        except (OSError, ValueError):
            return False
        return True


def _request_process_stop(process: subprocess.Popen[str]) -> None:
    """Beendet einen lokalen Erkenner begrenzt und ohne Rohfehlerausgabe."""
    try:
        if process.poll() is None and process.stdin is not None:
            process.stdin.write("STOP\n")
            process.stdin.flush()
        process.wait(timeout=1.0)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        try:
            process.terminate()
        except OSError:
            pass


def _capture_command(timeout: float, free_text: bool) -> str:
    """Formt eine validierte Sekundenfrist in einen festen Millisekundenbefehl um."""
    mode = "CONVERSATION" if free_text else "CONFIRMATION"
    return f"CAPTURE {mode} {round(timeout * 1000)}"


def _decode_transcript(payload: str) -> str | None:
    """Dekodiert ausschließlich eine begrenzte UTF-8-Erkennungsantwort."""
    if not payload:
        return None
    try:
        text = base64.b64decode(payload, validate=True).decode("utf-8").strip()
    except (ValueError, UnicodeError):
        raise _unavailable() from None
    return text[:MAX_TRANSCRIPT_CHARACTERS] or None


def _unavailable() -> FollowUpCaptureUnavailable:
    """Erzeugt eine konstante inhaltsfreie Fehlermeldung für den Dialog."""
    return FollowUpCaptureUnavailable("Local follow-up capture is unavailable.")


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


def _server_script(culture: str, confidence: float) -> str:
    """Setzt nur validierte Kultur und Konfidenz in das feste Serverskript ein."""
    script = _SERVER_SCRIPT.replace("__CULTURE__", _safe_culture(culture))
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
