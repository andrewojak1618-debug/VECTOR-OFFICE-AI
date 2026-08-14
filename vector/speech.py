"""German speech synthesis and Vector audio preparation."""

import base64
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

from vector.sdk_client import VectorSDKClient


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

$synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices |
    Where-Object DisplayName -eq $voiceName |
    Where-Object Language -eq 'de-DE' |
    Select-Object -First 1

if ($null -eq $voice) {
    throw "German TTS voice not found: $voiceName"
}

$synth.Voice = $voice
$operation = $synth.SynthesizeTextToStreamAsync($text)
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
        self.vector_client = vector_client
        self.voice = voice
        self.volume = volume

    def say(self, text: str) -> bool:
        """Synthesize and play one non-empty German utterance."""
        if not text.strip():
            print("Speech text must not be empty.")
            return False
        try:
            return self._prepare_and_play(text)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            print("German speech generation failed.")
            print(f"Reason: {exc}")
            return False

    def _prepare_and_play(self, text: str) -> bool:
        with tempfile.TemporaryDirectory(prefix="vector-speech-") as temp_dir:
            source_path = Path(temp_dir) / "source.wav"
            vector_path = Path(temp_dir) / "vector.wav"
            self._synthesize_german_wav(text, source_path)
            self._convert_for_vector(source_path, vector_path)
            self._validate_vector_wav(vector_path)
            return self.vector_client.play_wav(vector_path, volume=self.volume)

    def _synthesize_german_wav(self, text: str, output_path: Path) -> None:
        powershell = self._require_executable(
            "powershell",
            "Windows PowerShell is required for German TTS.",
        )
        script = self._create_tts_script(text, output_path)
        result = self._run_process(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", script]
        )
        self._require_output(result, output_path, "Windows TTS")

    def _create_tts_script(self, text: str, output_path: Path) -> str:
        replacements = {
            "__TEXT__": self._encode(text),
            "__VOICE__": self._encode(self.voice),
            "__OUTPUT__": self._encode(str(output_path)),
        }
        script = ONECORE_TTS_SCRIPT
        for marker, value in replacements.items():
            script = script.replace(marker, value)
        return script

    @staticmethod
    def _encode(value: str) -> str:
        return base64.b64encode(value.encode("utf-8")).decode("ascii")

    @classmethod
    def _convert_for_vector(cls, source_path: Path, output_path: Path) -> None:
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
        return [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(source_path), "-af", cls.VECTOR_AUDIO_FILTER,
            "-ar", str(cls.SAMPLE_RATE), "-ac", str(cls.CHANNELS),
            "-c:a", "pcm_s16le", str(output_path),
        ]

    @staticmethod
    def _require_executable(name: str, error_message: str) -> str:
        executable = shutil.which(name)
        if executable is None:
            raise RuntimeError(error_message)
        return executable

    @staticmethod
    def _run_process(arguments: list[str]) -> subprocess.CompletedProcess[str]:
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
        if result.returncode == 0 and output_path.is_file():
            return
        reason = result.stderr.strip() or f"{producer} produced no audio file."
        raise RuntimeError(reason)

    @classmethod
    def _validate_vector_wav(cls, audio_path: Path) -> None:
        with wave.open(str(audio_path), "rb") as wav_file:
            is_valid = (
                wav_file.getnchannels() == cls.CHANNELS
                and wav_file.getsampwidth() == cls.SAMPLE_WIDTH
                and wav_file.getframerate() == cls.SAMPLE_RATE
            )
        if not is_valid:
            raise RuntimeError("Vector audio must be 16 kHz, 16-bit, mono PCM WAV.")
