import base64
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

from vector.sdk_client import VectorSDKClient


class VectorSpeech:
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
        if not text.strip():
            print("Speech text must not be empty.")
            return False

        try:
            with tempfile.TemporaryDirectory(prefix="vector-speech-") as temp_dir:
                temp_path = Path(temp_dir)
                source_path = temp_path / "source.wav"
                vector_path = temp_path / "vector.wav"

                self._synthesize_german_wav(text, source_path)
                self._convert_for_vector(source_path, vector_path)
                self._validate_vector_wav(vector_path)

                return self.vector_client.play_wav(
                    vector_path,
                    volume=self.volume,
                )

        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            print("German speech generation failed.")
            print(f"Reason: {exc}")
            return False

    def _synthesize_german_wav(self, text: str, output_path: Path) -> None:
        powershell = shutil.which("powershell")

        if powershell is None:
            raise RuntimeError("Windows PowerShell is required for German TTS.")

        encoded_text = base64.b64encode(text.encode("utf-8")).decode("ascii")
        encoded_voice = base64.b64encode(self.voice.encode("utf-8")).decode("ascii")
        encoded_output = base64.b64encode(
            str(output_path).encode("utf-8")
        ).decode("ascii")

        script = f"""
        Add-Type -AssemblyName System.Runtime.WindowsRuntime
        [void][Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime]

        $text = [Text.Encoding]::UTF8.GetString(
            [Convert]::FromBase64String('{encoded_text}')
        )
        $voiceName = [Text.Encoding]::UTF8.GetString(
            [Convert]::FromBase64String('{encoded_voice}')
        )
        $outputPath = [Text.Encoding]::UTF8.GetString(
            [Convert]::FromBase64String('{encoded_output}')
        )

        $synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
        $voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices |
            Where-Object DisplayName -eq $voiceName |
            Where-Object Language -eq 'de-DE' |
            Select-Object -First 1

        if ($null -eq $voice) {{
            throw "German TTS voice not found: $voiceName"
        }}

        $synth.Voice = $voice
        $operation = $synth.SynthesizeTextToStreamAsync($text)
        $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() |
            Where-Object {{
                $_.Name -eq 'AsTask' -and
                $_.IsGenericMethod -and
                $_.GetParameters().Count -eq 1
            }} |
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

        try {{
            $inputStream.CopyTo($fileStream)
        }} finally {{
            $fileStream.Dispose()
            $inputStream.Dispose()
            $speechStream.Dispose()
            $synth.Dispose()
        }}
        """

        result = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        if result.returncode != 0 or not output_path.is_file():
            reason = result.stderr.strip() or "Windows TTS produced no audio file."
            raise RuntimeError(reason)

    @staticmethod
    def _convert_for_vector(source_path: Path, output_path: Path) -> None:
        ffmpeg = shutil.which("ffmpeg")

        if ffmpeg is None:
            raise RuntimeError("FFmpeg is required to prepare audio for Vector.")

        result = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source_path),
                "-af",
                VectorSpeech.VECTOR_AUDIO_FILTER,
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        if result.returncode != 0 or not output_path.is_file():
            reason = result.stderr.strip() or "FFmpeg produced no Vector audio file."
            raise RuntimeError(reason)

    @staticmethod
    def _validate_vector_wav(audio_path: Path) -> None:
        with wave.open(str(audio_path), "rb") as wav_file:
            is_valid = (
                wav_file.getnchannels() == 1
                and wav_file.getsampwidth() == 2
                and wav_file.getframerate() == 16000
            )

        if not is_valid:
            raise RuntimeError(
                "Vector audio must be 16 kHz, 16-bit, mono PCM WAV."
            )
