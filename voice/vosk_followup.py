"""Erfasst kurze deutsche Folgeantworten vollständig lokal mit Vosk."""

import importlib
import json
import math
import queue
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from application.voice_followup import FollowUpCaptureUnavailable


MIN_CAPTURE_TIMEOUT_SECONDS = 1.0
MAX_CAPTURE_TIMEOUT_SECONDS = 10.0
MAX_TRANSCRIPT_CHARACTERS = 240
AUDIO_BLOCK_SIZE = 8_000
CONFIRMATION_PHRASES = (
    "ja",
    "ja bitte",
    "ja bitte öffnen",
    "ja bitte ausführen",
    "ja den ordner bitte öffnen",
    "ja die datei bitte öffnen",
    "bestätigen",
    "bitte bestätigen",
    "ausführen",
    "nein",
    "nein danke",
    "abbrechen",
    "stopp",
    "nicht ausführen",
)
MODEL_MARKERS = (
    Path("am/final.mdl"),
    Path("conf/mfcc.conf"),
    Path("graph/HCLr.fst"),
)


class VoskFollowUpCapture:
    """Hält ein deutsches Vosk-Modell für begrenzte Folgeantworten bereit."""

    def __init__(
        self,
        model_path: str | Path,
        min_confidence: float = 0.15,
        audio_device: str | int | None = None,
        dependency_loader: Callable[[], tuple[Any, Any, Any]] | None = None,
    ):
        """Initialisiert Modell-, Geräte- und Konfidenzgrenzen ohne Aufnahme."""
        if not _valid_confidence(min_confidence):
            raise ValueError("Follow-up confidence must be between 0 and 1.")
        self.model_path = Path(model_path).expanduser()
        self.min_confidence = min_confidence
        self.audio_device = audio_device
        self.dependency_loader = dependency_loader or _load_dependencies
        self._model_type: Any = None
        self._recognizer_type: Any = None
        self._sounddevice: Any = None
        self._model: Any = None
        self._sample_rate: float | None = None

    def prepare(self) -> bool:
        """Lädt Modell und Audiogerät lokal, ohne das Mikrofon zu öffnen."""
        if self._model is not None:
            return True
        if not _valid_model_path(self.model_path):
            return False
        try:
            dependencies = self.dependency_loader()
            model_type, recognizer_type, sounddevice = dependencies
            sample_rate = _input_sample_rate(sounddevice, self.audio_device)
            model = model_type(str(self.model_path.resolve()))
        except (ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError):
            self.close()
            return False
        self._model_type = model_type
        self._recognizer_type = recognizer_type
        self._sounddevice = sounddevice
        self._sample_rate = sample_rate
        self._model = model
        return True

    def capture(self, timeout: float, free_text: bool = False) -> str | None:
        """Erkennt genau eine lokale Antwort und verwirft die Audiodaten danach."""
        if not _valid_timeout(timeout):
            raise ValueError("Follow-up timeout must be between 1 and 10 seconds.")
        if not isinstance(free_text, bool):
            raise TypeError("Follow-up mode must be a boolean.")
        if not self.prepare():
            raise _unavailable()
        recognizer = self._create_recognizer(free_text)
        audio_chunks: queue.Queue[bytes] = queue.Queue()
        try:
            payload = self._capture_payload(recognizer, audio_chunks, timeout)
        except (OSError, RuntimeError, TypeError, ValueError):
            raise _unavailable() from None
        finally:
            _clear_queue(audio_chunks)
        return _recognized_text(payload, self.min_confidence)

    def close(self) -> None:
        """Gibt Modell- und Audioreferenzen frei, ohne Inhalte zu speichern."""
        self._model = None
        self._sample_rate = None
        self._model_type = None
        self._recognizer_type = None
        self._sounddevice = None

    def _create_recognizer(self, free_text: bool) -> Any:
        """Erzeugt freie Erkennung oder eine begrenzte Bestätigungsgrammatik."""
        if free_text:
            recognizer = self._recognizer_type(self._model, self._sample_rate)
        else:
            grammar = json.dumps(CONFIRMATION_PHRASES, ensure_ascii=False)
            recognizer = self._recognizer_type(
                self._model,
                self._sample_rate,
                grammar,
            )
        recognizer.SetWords(True)
        return recognizer

    def _capture_payload(
        self,
        recognizer: Any,
        audio_chunks: queue.Queue[bytes],
        timeout: float,
    ) -> str:
        """Öffnet das Mikrofon zeitlich begrenzt und liefert nur Vosk-JSON."""
        def collect_audio(indata, _frames, _time_info, _status) -> None:
            """Überträgt flüchtige Audioblöcke ausschließlich in den Arbeitsspeicher."""
            audio_chunks.put(bytes(indata))

        options = {
            "samplerate": self._sample_rate,
            "blocksize": AUDIO_BLOCK_SIZE,
            "device": self.audio_device,
            "dtype": "int16",
            "channels": 1,
            "callback": collect_audio,
        }
        with self._sounddevice.RawInputStream(**options):
            return _recognize_until_timeout(recognizer, audio_chunks, timeout)


def _load_dependencies() -> tuple[Any, Any, Any]:
    """Lädt Vosk und PortAudio erst bei aktivierter lokaler Folgeaufnahme."""
    vosk = importlib.import_module("vosk")
    sounddevice = importlib.import_module("sounddevice")
    vosk.SetLogLevel(-1)
    return vosk.Model, vosk.KaldiRecognizer, sounddevice


def _input_sample_rate(sounddevice: Any, device: str | int | None) -> float:
    """Ermittelt eine gültige Abtastrate des ausgewählten Eingabegeräts."""
    information = sounddevice.query_devices(device, kind="input")
    channels = int(information["max_input_channels"])
    sample_rate = float(information["default_samplerate"])
    if channels < 1 or not math.isfinite(sample_rate) or sample_rate <= 0:
        raise ValueError("No valid local input device is available.")
    return sample_rate


def _recognize_until_timeout(
    recognizer: Any,
    audio_chunks: queue.Queue[bytes],
    timeout: float,
) -> str:
    """Verarbeitet flüchtige Audioblöcke bis zum Satzende oder zur Frist."""
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return recognizer.FinalResult()
        try:
            audio = audio_chunks.get(timeout=min(0.25, remaining))
        except queue.Empty:
            continue
        if recognizer.AcceptWaveform(audio):
            return recognizer.Result()


def _recognized_text(payload: str, min_confidence: float) -> str | None:
    """Prüft Vosk-JSON und gibt nur ausreichend sichere kurze Texte weiter."""
    try:
        result = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(result, dict) or not _confident(result, min_confidence):
        return None
    text = result.get("text")
    if not isinstance(text, str):
        return None
    return text.strip()[:MAX_TRANSCRIPT_CHARACTERS] or None


def _confident(result: dict[str, Any], minimum: float) -> bool:
    """Bewertet ausschließlich endliche Wortkonfidenzen aus dem lokalen Ergebnis."""
    words = result.get("result")
    if not isinstance(words, list) or not words:
        return False
    confidences = [word.get("conf") for word in words if isinstance(word, dict)]
    if len(confidences) != len(words) or not all(_valid_confidence(c) for c in confidences):
        return False
    return sum(confidences) / len(confidences) >= minimum


def _clear_queue(audio_chunks: queue.Queue[bytes]) -> None:
    """Entfernt alle noch gepufferten Audioblöcke unmittelbar nach der Erkennung."""
    while True:
        try:
            audio_chunks.get_nowait()
        except queue.Empty:
            return


def _valid_model_path(model_path: Path) -> bool:
    """Prüft die minimal erforderlichen Dateien eines entpackten Vosk-Modells."""
    return model_path.is_dir() and all(
        (model_path / marker).is_file() for marker in MODEL_MARKERS
    )


def _unavailable() -> FollowUpCaptureUnavailable:
    """Erzeugt eine konstante inhaltsfreie Fehlermeldung für den Dialog."""
    return FollowUpCaptureUnavailable("Local follow-up capture is unavailable.")


def _valid_timeout(value: float) -> bool:
    """Prüft eine endliche Aufnahmefrist gegen die Dialoggrenze."""
    return (
        isinstance(value, (int, float))
        and math.isfinite(value)
        and MIN_CAPTURE_TIMEOUT_SECONDS <= value <= MAX_CAPTURE_TIMEOUT_SECONDS
    )


def _valid_confidence(value: float) -> bool:
    """Prüft eine endliche Konfidenz gegen den zulässigen Wertebereich."""
    return (
        isinstance(value, (int, float))
        and math.isfinite(value)
        and 0.0 <= value <= 1.0
    )
