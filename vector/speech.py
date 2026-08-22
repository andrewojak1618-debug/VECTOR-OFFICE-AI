"""German speech synthesis and Vector audio preparation."""

import base64
import secrets
import shutil
import subprocess
import tempfile
import threading
import wave
from dataclasses import dataclass
from pathlib import Path

from vector.sdk_client import VectorSDKClient
from vector.speech_prosody import (
    REFLECTIVE_RATE,
    SpeechStyle,
    build_speech_content,
)


ONECORE_TTS_SCRIPT = r"""
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[void][Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime]

$text = [Text.Encoding]::UTF8.GetString(
    [Convert]::FromBase64String('__TEXT__')
)
$voiceName = [Text.Encoding]::UTF8.GetString(
    [Convert]::FromBase64String('__VOICE__')
)
$outputPath = [Text.Encoding]::UTF8.GetString(
    [Convert]::FromBase64String('__OUTPUT__')
)
$isSsml = '__IS_SSML__' -eq 'true'

$synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices |
    Where-Object DisplayName -eq $voiceName |
    Where-Object Language -eq 'de-DE' |
    Select-Object -First 1

if ($null -eq $voice) {
    throw "German TTS voice not found: $voiceName"
}

$synth.Voice = $voice
if ($isSsml) {
    $operation = $synth.SynthesizeSsmlToStreamAsync($text)
} else {
    $operation = $synth.SynthesizeTextToStreamAsync($text)
}
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object {
        $_.Name -eq 'AsTask' -and
        $_.IsGenericMethod -and
        $_.GetParameters().Count -eq 1
    } |
    Select-Object -First 1
$task = $asTask.MakeGenericMethod(
    [Windows.Media.SpeechSynthesis.SpeechSynthesisStream]
).Invoke($null, @($operation))
$task.Wait()

$speechStream = $task.Result
$inputStream = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead(
    $speechStream
)
$fileStream = [System.IO.File]::Create($outputPath)

try {
    $inputStream.CopyTo($fileStream)
} finally {
    $fileStream.Dispose()
    $inputStream.Dispose()
    $speechStream.Dispose()
    $synth.Dispose()
}
"""


REFLECTIVE_LEADING_BREAK_MS = 180
REFLECTIVE_HUM_RATE = "-32%"


@dataclass(frozen=True)
class _ReflectivePrelude:
    label: str
    markup: str
    break_ms: int


class PreparedSpeech:
    """Own one validated temporary WAV until it has been played or closed."""

    def __init__(self, workspace: tempfile.TemporaryDirectory, path: Path):
        """Übernimmt den temporären Arbeitsbereich einer validierten WAV-Datei."""
        self.path = path
        self._workspace = workspace

    def close(self) -> None:
        """Löscht den temporären Audioarbeitsbereich genau einmal."""
        workspace = self._workspace
        self._workspace = None
        if workspace is not None:
            workspace.cleanup()


REFLECTIVE_PRELUDES = (
    _ReflectivePrelude(
        "IPA-Summton",
        f'<prosody rate="{REFLECTIVE_HUM_RATE}">'
        '<phoneme alphabet="ipa" ph="mː">mmm</phoneme></prosody>',
        1500,
    ),
    _ReflectivePrelude("Ich schätze", "Ich schätze", 320),
    _ReflectivePrelude(
        "Lass mich überlegen",
        "Lass mich überlegen",
        2000,
    ),
)


class VectorSpeech:
    """Synthesize German speech and stream validated WAV audio to Vector."""

    SAMPLE_RATE = 16000
    CHANNELS = 1
    SAMPLE_WIDTH = 2
    VECTOR_AUDIO_FILTER = (
        "acompressor="
        "threshold=-20dB:ratio=3:attack=5:release=100:makeup=3dB,"
        "loudnorm=I=-14:TP=-1:LRA=5"
    )

    def __init__(
        self,
        vector_client: VectorSDKClient,
        voice: str = "Microsoft Stefan",
        volume: int = 50,
    ):
        """Initialisiert deutsche TTS mit lokaler Stimme, Lautstärke und Synthesesperre."""
        self.vector_client = vector_client
        self.voice = voice
        self.volume = volume
        self._synthesis_lock = threading.Lock()

    def say(
        self,
        text: str,
        style: SpeechStyle = SpeechStyle.CONVERSATIONAL,
    ) -> bool:
        """Synthetisiert und spricht eine nicht leere deutsche Äußerung."""
        if not isinstance(text, str) or not text.strip():
            print("Speech text must not be empty.")
            return False
        if not isinstance(style, SpeechStyle):
            raise TypeError("Speech style must be a SpeechStyle value.")
        try:
            return self.play_prepared(self.prepare(text, style))
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            print("German speech generation failed.")
            print(f"Reason: {exc}")
            return False

    def prepare(
        self,
        text: str,
        style: SpeechStyle = SpeechStyle.CONVERSATIONAL,
    ) -> PreparedSpeech:
        """Synthetisiert und validiert eine Äußerung ohne Wiedergabestart."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Prepared speech text must not be empty.")
        if not isinstance(style, SpeechStyle):
            raise TypeError("Speech style must be a SpeechStyle value.")
        workspace = tempfile.TemporaryDirectory(prefix="vector-speech-")
        source_path = Path(workspace.name) / self._source_filename()
        vector_path = Path(workspace.name) / "vector.wav"
        try:
            self._synthesize_german_wav(text, source_path, style)
            self._convert_for_vector(source_path, vector_path)
            self._validate_vector_wav(vector_path)
        except (OSError, RuntimeError, subprocess.SubprocessError, wave.Error):
            workspace.cleanup()
            raise
        return PreparedSpeech(workspace, vector_path)

    def _source_filename(self) -> str:
        """Liefert den festen Dateinamen des lokalen Syntheseformats."""
        return "source.wav"

    def play_prepared(self, prepared: PreparedSpeech) -> bool:
        """Spielt eine vorbereitete Äußerung und gibt ihre Dateien stets frei."""
        if not isinstance(prepared, PreparedSpeech):
            raise TypeError("Prepared speech has an invalid type.")
        try:
            return self.vector_client.play_wav(
                prepared.path,
                volume=self.volume,
            )
        finally:
            prepared.close()

    def say_thinking_prelude(self) -> bool:
        """Wählt und spricht eine lokale Denkphase vor der Antwort."""
        try:
            prelude = secrets.choice(REFLECTIVE_PRELUDES)
            return self._prepare_ssml_and_play(self._thinking_content(prelude))
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            print("German thinking prelude generation failed.")
            print(f"Reason: {exc}")
            return False

    def _prepare_ssml_and_play(self, content: str) -> bool:
        """Synthetisiert SSML temporär, wandelt es um und spielt es über Vector."""
        with tempfile.TemporaryDirectory(prefix="vector-speech-") as temp_dir:
            source_path = Path(temp_dir) / "source.wav"
            vector_path = Path(temp_dir) / "vector.wav"
            self._synthesize_german_ssml_wav(content, source_path)
            self._convert_for_vector(source_path, vector_path)
            self._validate_vector_wav(vector_path)
            return self.vector_client.play_wav(vector_path, volume=self.volume)

    def _synthesize_german_wav(
        self,
        text: str,
        output_path: Path,
        style: SpeechStyle = SpeechStyle.CONVERSATIONAL,
    ) -> None:
        """Erzeugt aus deutschem Text und festem Stil eine lokale WAV-Quelle."""
        content = self._speech_content(text, style)
        self._synthesize_german_ssml_wav(content, output_path)

    def _synthesize_german_ssml_wav(
        self,
        content: str,
        output_path: Path,
    ) -> None:
        """Synthetisiert deutsches SSML seriell und verlangt eine Ausgabedatei."""
        with self._synthesis_lock:
            result = self._run_synthesis(content, output_path)
        self._require_output(result, output_path, "Windows TTS")

    def _run_synthesis(
        self,
        content: str,
        output_path: Path,
    ) -> subprocess.CompletedProcess[str]:
        """Führt die lokale Windows-TTS-Synthese ohne sichtbares Fenster aus."""
        powershell = self._require_executable(
            "powershell",
            "Windows PowerShell is required for German TTS.",
        )
        script = self._create_tts_script_for_content(content, output_path)
        return self._run_process(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", script]
        )

    def _create_tts_script(
        self,
        text: str,
        output_path: Path,
        style: SpeechStyle = SpeechStyle.CONVERSATIONAL,
    ) -> str:
        """Erzeugt ein lokales TTS-Skript aus Text und festem Sprachstil."""
        content = self._speech_content(text, style)
        return self._create_tts_script_for_content(content, output_path)

    def _create_tts_script_for_content(
        self,
        content: str,
        output_path: Path,
    ) -> str:
        """Setzt Base64-kodierte Werte sicher in die feste Skriptvorlage ein."""
        replacements = {
            "__TEXT__": self._encode(content),
            "__VOICE__": self._encode(self.voice),
            "__OUTPUT__": self._encode(str(output_path)),
            "__IS_SSML__": "true",
        }
        script = ONECORE_TTS_SCRIPT
        for marker, value in replacements.items():
            script = script.replace(marker, value)
        return script

    @staticmethod
    def _speech_content(text: str, style: SpeechStyle) -> str:
        """Erzeugt kontrolliertes SSML für den ausgewählten Sprachstil."""
        return build_speech_content(text, style)

    @staticmethod
    def _thinking_content(prelude: _ReflectivePrelude) -> str:
        """Erzeugt SSML für eine begrenzte Denkphrase samt festgelegter Pause."""
        return (
            '<speak version="1.0" '
            'xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="de-DE">'
            f'<prosody rate="{REFLECTIVE_RATE}">'
            f'<break time="{REFLECTIVE_LEADING_BREAK_MS}ms"/>'
            f'{prelude.markup}<break time="{prelude.break_ms}ms"/>'
            "</prosody></speak>"
        )

    @staticmethod
    def _encode(value: str) -> str:
        """Kodiert einen UTF-8-Wert für die sichere Skriptübergabe als Base64."""
        return base64.b64encode(value.encode("utf-8")).decode("ascii")

    @classmethod
    def _convert_for_vector(cls, source_path: Path, output_path: Path) -> None:
        """Konvertiert Quellaudio in Vectors validiertes PCM-WAV-Format."""
        ffmpeg = cls._require_executable(
            "ffmpeg",
            "FFmpeg is required to prepare audio for Vector.",
        )
        result = cls._run_process(cls._ffmpeg_arguments(ffmpeg, source_path, output_path))
        cls._require_output(result, output_path, "FFmpeg")

    @classmethod
    def _ffmpeg_arguments(
        cls,
        ffmpeg: str,
        source_path: Path,
        output_path: Path,
    ) -> list[str]:
        """Erzeugt die feste FFmpeg-Argumentliste mit Kompression und Pegelnormalisierung."""
        return [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(source_path), "-af", cls.VECTOR_AUDIO_FILTER,
            "-ar", str(cls.SAMPLE_RATE), "-ac", str(cls.CHANNELS),
            "-c:a", "pcm_s16le", str(output_path),
        ]

    @staticmethod
    def _require_executable(name: str, error_message: str) -> str:
        """Löst ein benötigtes lokales Programm auf oder bricht verständlich ab."""
        executable = shutil.which(name)
        if executable is None:
            raise RuntimeError(error_message)
        return executable

    @staticmethod
    def _run_process(arguments: list[str]) -> subprocess.CompletedProcess[str]:
        """Führt einen lokalen Audioprozess verborgen und ohne Ausnahme bei Statuscode aus."""
        return subprocess.run(
            arguments,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    @staticmethod
    def _require_output(
        result: subprocess.CompletedProcess[str],
        output_path: Path,
        producer: str,
    ) -> None:
        """Verlangt einen erfolgreichen Prozess und eine vorhandene Ausgabedatei."""
        if result.returncode == 0 and output_path.is_file():
            return
        reason = result.stderr.strip() or f"{producer} produced no audio file."
        raise RuntimeError(reason)

    @classmethod
    def _validate_vector_wav(cls, audio_path: Path) -> None:
        """Prüft Kanalzahl, Samplebreite und Rate gegen Vectors Audioformat."""
        with wave.open(str(audio_path), "rb") as wav_file:
            is_valid = (
                wav_file.getnchannels() == cls.CHANNELS
                and wav_file.getsampwidth() == cls.SAMPLE_WIDTH
                and wav_file.getframerate() == cls.SAMPLE_RATE
            )
        if not is_valid:
            raise RuntimeError("Vector audio must be 16 kHz, 16-bit, mono PCM WAV.")
