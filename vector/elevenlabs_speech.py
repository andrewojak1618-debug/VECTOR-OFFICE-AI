"""Optional ElevenLabs German speech with a local OneCore fallback."""

import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

import httpx

from vector.speech import PreparedSpeech, VectorSpeech
from vector.speech_prosody import SpeechStyle, normalize_speech_text


ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVENLABS_OUTPUT_FORMAT = "mp3_22050_32"
NATURAL_VECTOR_AUDIO_FILTER = "loudnorm=I=-14:TP=-1:LRA=9"


@dataclass(frozen=True)
class ElevenLabsVoiceSettings:
    """Hold bounded voice controls for one ElevenLabs speech provider."""

    stability: float = 0.45
    similarity: float = 0.75
    style: float = 0.0
    speed: float = 1.02

    def __post_init__(self) -> None:
        for name in ("stability", "similarity", "style"):
            if not 0.0 <= getattr(self, name) <= 1.0:
                raise ValueError(f"ElevenLabs {name} must be between 0 and 1.")
        if not 0.7 <= self.speed <= 1.2:
            raise ValueError("ElevenLabs speed must be between 0.7 and 1.2.")

    def payload(self) -> dict[str, float | bool]:
        """Return the API voice-settings object without any secret values."""
        return {
            "stability": self.stability,
            "similarity_boost": self.similarity,
            "style": self.style,
            "use_speaker_boost": True,
            "speed": self.speed,
        }


class ElevenLabsSpeech(VectorSpeech):
    """Generate the main answer in ElevenLabs and fall back to local German."""

    VECTOR_AUDIO_FILTER = NATURAL_VECTOR_AUDIO_FILTER

    def __init__(
        self,
        local_speech: VectorSpeech,
        api_key: str,
        voice_id: str,
        model: str = "eleven_flash_v2_5",
        timeout: float = 15.0,
        voice_settings: ElevenLabsVoiceSettings | None = None,
        client: httpx.Client | None = None,
    ):
        self._validate_configuration(api_key, voice_id, model, timeout)
        super().__init__(
            local_speech.vector_client,
            local_speech.voice,
            local_speech.volume,
        )
        self.local_speech = local_speech
        self.api_key = api_key.strip()
        self.voice_id = voice_id.strip()
        self.model = model.strip()
        self.voice_settings = voice_settings or ElevenLabsVoiceSettings()
        self.client = client or httpx.Client(timeout=timeout)

    def prepare(
        self,
        text: str,
        style: SpeechStyle = SpeechStyle.CONVERSATIONAL,
    ) -> PreparedSpeech:
        """Prepare cloud speech or transparently use the local voice."""
        try:
            return super().prepare(text, style)
        except (
            OSError,
            RuntimeError,
            subprocess.SubprocessError,
            wave.Error,
        ):
            print("ElevenLabs speech unavailable. Using local German voice.")
            return self.local_speech.prepare(text, style)

    def say_thinking_prelude(self) -> bool:
        """Keep the thinking prelude local, private, and immediately available."""
        return self.local_speech.say_thinking_prelude()

    def _source_filename(self) -> str:
        return "source.mp3"

    def _synthesize_german_wav(
        self,
        text: str,
        output_path: Path,
        style: SpeechStyle = SpeechStyle.CONVERSATIONAL,
    ) -> None:
        del style
        output_path.write_bytes(self._request_audio(normalize_speech_text(text)))

    def _request_audio(self, text: str) -> bytes:
        try:
            response = self.client.post(
                f"{ELEVENLABS_TTS_URL}/{self.voice_id}",
                params={"output_format": ELEVENLABS_OUTPUT_FORMAT},
                headers={"xi-api-key": self.api_key},
                json=self._request_payload(text),
            )
        except httpx.HTTPError as exc:
            raise RuntimeError("ElevenLabs TTS request could not be completed.") from exc
        if response.status_code != 200:
            raise RuntimeError(
                f"ElevenLabs TTS request failed with status {response.status_code}."
            )
        if len(response.content) < 16:
            raise RuntimeError("ElevenLabs returned an invalid audio response.")
        return bytes(response.content)

    def _request_payload(self, text: str) -> dict:
        return {
            "text": text,
            "model_id": self.model,
            "apply_text_normalization": "auto",
            "voice_settings": self.voice_settings.payload(),
        }

    @staticmethod
    def _validate_configuration(
        api_key: str,
        voice_id: str,
        model: str,
        timeout: float,
    ) -> None:
        values = (api_key, voice_id, model)
        if not all(isinstance(value, str) and value.strip() for value in values):
            raise ValueError("ElevenLabs key, voice ID, and model are required.")
        if not 1.0 <= timeout <= 60.0:
            raise ValueError("ElevenLabs timeout must be between 1 and 60 seconds.")
