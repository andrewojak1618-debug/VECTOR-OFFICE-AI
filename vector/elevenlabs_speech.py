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
SUPPORTIVE_STABILITY_OFFSET = -0.08
SUPPORTIVE_SPEED_OFFSET = -0.03
CAUTIOUS_STABILITY_OFFSET = 0.07
CAUTIOUS_SPEED_OFFSET = -0.01


class ElevenLabsTimeoutError(RuntimeError):
    """Meldet eine ElevenLabs-Frist ohne Anfrageinhalte offenzulegen."""


@dataclass(frozen=True)
class ElevenLabsVoiceSettings:
    """Hold bounded voice controls for one ElevenLabs speech provider."""

    stability: float = 0.45
    similarity: float = 0.75
    style: float = 0.0
    speed: float = 1.02

    def __post_init__(self) -> None:
        """Validiert alle Cloud-Stimmwerte innerhalb enger sicherer Grenzen."""
        for name in ("stability", "similarity", "style"):
            if not 0.0 <= getattr(self, name) <= 1.0:
                raise ValueError(f"ElevenLabs {name} must be between 0 and 1.")
        if not 0.7 <= self.speed <= 1.2:
            raise ValueError("ElevenLabs speed must be between 0.7 and 1.2.")

    def payload(self) -> dict[str, float | bool]:
        """Liefert die API-Stimmeinstellungen ohne geheime Werte."""
        return {
            "stability": self.stability,
            "similarity_boost": self.similarity,
            "style": self.style,
            "use_speaker_boost": True,
            "speed": self.speed,
        }

    def for_speech_style(
        self,
        speech_style: SpeechStyle,
    ) -> "ElevenLabsVoiceSettings":
        """Liefert eine eng angepasste Kopie für eine transparente Sprechhaltung."""
        if speech_style is SpeechStyle.SUPPORTIVE:
            return self._adjusted(
                stability=SUPPORTIVE_STABILITY_OFFSET,
                speed=SUPPORTIVE_SPEED_OFFSET,
            )
        if speech_style is SpeechStyle.CAUTIOUS:
            return self._adjusted(
                stability=CAUTIOUS_STABILITY_OFFSET,
                speed=CAUTIOUS_SPEED_OFFSET,
            )
        return self

    def _adjusted(
        self,
        *,
        stability: float,
        speed: float,
    ) -> "ElevenLabsVoiceSettings":
        """Begrenzt relative Stabilitäts- und Geschwindigkeitsänderungen auf API-Werte."""
        return ElevenLabsVoiceSettings(
            stability=min(1.0, max(0.0, self.stability + stability)),
            similarity=self.similarity,
            style=self.style,
            speed=min(1.2, max(0.7, self.speed + speed)),
        )


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
        """Initialisiert Cloud-TTS mit validierter Konfiguration und lokalem Rückfall."""
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
        """Bereitet Cloud-Sprache vor oder nutzt transparent die lokale Stimme."""
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
        """Hält die Denkphase lokal, privat und unmittelbar verfügbar."""
        return self.local_speech.say_thinking_prelude()

    def _source_filename(self) -> str:
        """Liefert den festen Dateinamen des ElevenLabs-Quellformats."""
        return "source.mp3"

    def _synthesize_german_wav(
        self,
        text: str,
        output_path: Path,
        style: SpeechStyle = SpeechStyle.CONVERSATIONAL,
    ) -> None:
        """Ruft normalisierte deutsche Cloud-Sprache ab und schreibt temporäres Audio."""
        output_path.write_bytes(
            self._request_audio(normalize_speech_text(text), style)
        )

    def _request_audio(
        self,
        text: str,
        style: SpeechStyle = SpeechStyle.CONVERSATIONAL,
    ) -> bytes:
        """Fordert Audiodaten mit festem Ziel und ohne Protokollierung des Schlüssels an."""
        try:
            response = self.client.post(
                f"{ELEVENLABS_TTS_URL}/{self.voice_id}",
                params={"output_format": ELEVENLABS_OUTPUT_FORMAT},
                headers={"xi-api-key": self.api_key},
                json=self._request_payload(text, style),
            )
        except httpx.TimeoutException:
            raise ElevenLabsTimeoutError(
                "ElevenLabs TTS request timed out."
            ) from None
        except httpx.HTTPError as exc:
            raise RuntimeError("ElevenLabs TTS request could not be completed.") from exc
        if response.status_code != 200:
            raise RuntimeError(
                f"ElevenLabs TTS request failed with status {response.status_code}."
            )
        if len(response.content) < 16:
            raise RuntimeError("ElevenLabs returned an invalid audio response.")
        return bytes(response.content)

    def _request_payload(
        self,
        text: str,
        style: SpeechStyle = SpeechStyle.CONVERSATIONAL,
    ) -> dict:
        """Erzeugt die begrenzte ElevenLabs-Nutzlast für Text, Modell und Sprechstil."""
        voice_settings = self.voice_settings.for_speech_style(style)
        return {
            "text": text,
            "model_id": self.model,
            "apply_text_normalization": "auto",
            "voice_settings": voice_settings.payload(),
        }

    @staticmethod
    def _validate_configuration(
        api_key: str,
        voice_id: str,
        model: str,
        timeout: float,
    ) -> None:
        """Validiert Zugangsdatenfelder, Modell und Cloud-Anfragefrist."""
        values = (api_key, voice_id, model)
        if not all(isinstance(value, str) and value.strip() for value in values):
            raise ValueError("ElevenLabs key, voice ID, and model are required.")
        if not 1.0 <= timeout <= 60.0:
            raise ValueError("ElevenLabs timeout must be between 1 and 60 seconds.")
