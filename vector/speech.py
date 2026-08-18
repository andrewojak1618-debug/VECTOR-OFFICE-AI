"""German speech synthesis and Vector audio preparation."""

import base64
import re
import secrets
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from xml.sax.saxutils import escape

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


class SpeechStyle(Enum):
    """Select a bounded speech-synthesis profile for one utterance."""

    NEUTRAL = "neutral"
    REFLECTIVE = "reflective"


REFLECTIVE_SENTENCE_BREAK_MS = 190
REFLECTIVE_LEADING_BREAK_MS = 180
NEUTRAL_RATE = "+8%"
REFLECTIVE_RATE = "+5%"
REFLECTIVE_HUM_RATE = "-32%"
SENTENCE_OPENING_WORDS = 2
SENTENCE_ENDING_WORDS = 3


@dataclass(frozen=True)
class _ReflectivePrelude:
    label: str
    markup: str
    break_ms: int


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
        self.vector_client = vector_client
        self.voice = voice
        self.volume = volume

    def say(
        self,
        text: str,
        style: SpeechStyle = SpeechStyle.NEUTRAL,
    ) -> bool:
        """Synthesize and play one non-empty German utterance."""
        if not isinstance(text, str) or not text.strip():
            print("Speech text must not be empty.")
            return False
        if not isinstance(style, SpeechStyle):
            raise TypeError("Speech style must be a SpeechStyle value.")
        try:
            return self._prepare_and_play(text, style)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            print("German speech generation failed.")
            print(f"Reason: {exc}")
            return False

    def say_thinking_prelude(self) -> bool:
        """Select and play one local pre-response thinking phrase."""
        try:
            prelude = secrets.choice(REFLECTIVE_PRELUDES)
            return self._prepare_ssml_and_play(self._thinking_content(prelude))
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            print("German thinking prelude generation failed.")
            print(f"Reason: {exc}")
            return False

    def _prepare_and_play(self, text: str, style: SpeechStyle) -> bool:
        with tempfile.TemporaryDirectory(prefix="vector-speech-") as temp_dir:
            source_path = Path(temp_dir) / "source.wav"
            vector_path = Path(temp_dir) / "vector.wav"
            self._synthesize_german_wav(text, source_path, style)
            self._convert_for_vector(source_path, vector_path)
            self._validate_vector_wav(vector_path)
            return self.vector_client.play_wav(vector_path, volume=self.volume)

    def _prepare_ssml_and_play(self, content: str) -> bool:
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
        style: SpeechStyle = SpeechStyle.NEUTRAL,
    ) -> None:
        content = self._speech_content(text, style)
        self._synthesize_german_ssml_wav(content, output_path)

    def _synthesize_german_ssml_wav(
        self,
        content: str,
        output_path: Path,
    ) -> None:
        powershell = self._require_executable(
            "powershell",
            "Windows PowerShell is required for German TTS.",
        )
        script = self._create_tts_script_for_content(content, output_path)
        result = self._run_process(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", script]
        )
        self._require_output(result, output_path, "Windows TTS")

    def _create_tts_script(
        self,
        text: str,
        output_path: Path,
        style: SpeechStyle = SpeechStyle.NEUTRAL,
    ) -> str:
        content = self._speech_content(text, style)
        return self._create_tts_script_for_content(content, output_path)

    def _create_tts_script_for_content(
        self,
        content: str,
        output_path: Path,
    ) -> str:
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
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        pause = f'<break time="{REFLECTIVE_SENTENCE_BREAK_MS}ms"/>'
        body = pause.join(
            VectorSpeech._shape_sentence(sentence)
            for sentence in sentences
            if sentence
        )
        rate = NEUTRAL_RATE
        if style is SpeechStyle.REFLECTIVE:
            rate = REFLECTIVE_RATE
        return (
            '<speak version="1.0" '
            'xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="de-DE">'
            f'<prosody rate="{rate}">{body}'
            "</prosody></speak>"
        )

    @staticmethod
    def _thinking_content(prelude: _ReflectivePrelude) -> str:
        return (
            '<speak version="1.0" '
            'xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="de-DE">'
            f'<prosody rate="{REFLECTIVE_RATE}">'
            f'<break time="{REFLECTIVE_LEADING_BREAK_MS}ms"/>'
            f'{prelude.markup}<break time="{prelude.break_ms}ms"/>'
            "</prosody></speak>"
        )

    @staticmethod
    def _shape_sentence(sentence: str) -> str:
        """Give one sentence a present opening and a gently falling ending."""
        words = sentence.split()
        if not words:
            return ""
        if len(words) == 1:
            return (
                '<prosody volume="soft" pitch="-3%">'
                f'{escape(words[0])}</prosody>'
            )
        opening_count = min(SENTENCE_OPENING_WORDS, len(words) - 1)
        ending_count = min(SENTENCE_ENDING_WORDS, len(words) - opening_count)
        opening = escape(" ".join(words[:opening_count]))
        middle = escape(" ".join(words[opening_count:-ending_count]))
        ending = escape(" ".join(words[-ending_count:]))
        parts = [
            '<prosody volume="loud" pitch="+3%">'
            f'{opening}</prosody>'
        ]
        if middle:
            parts.append(middle)
        parts.append(
            '<prosody volume="soft" pitch="-5%">'
            f'{ending}</prosody>'
        )
        return " ".join(parts)

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
