"""Compose the configured German speech provider with safe cloud defaults."""

from diagnostics.events import StructuredDiagnosticReporter
from vector.elevenlabs_speech import ElevenLabsSpeech, ElevenLabsVoiceSettings
from vector.sdk_client import VectorSDKClient
from vector.speech import VectorSpeech


def create_speech_output(
    settings,
    vector: VectorSDKClient,
    diagnostics: StructuredDiagnosticReporter | None = None,
) -> VectorSpeech:
    """Erzeugt lokale Sprache oder ausdrücklich freigegebenes ElevenLabs mit Rückfall."""
    local = VectorSpeech(vector, settings.TTS_VOICE, settings.TTS_VOLUME)
    provider = getattr(settings, "TTS_PROVIDER", "onecore").casefold().strip()
    if provider == "onecore":
        return local
    if provider != "elevenlabs":
        raise ValueError("TTS_PROVIDER must be either 'onecore' or 'elevenlabs'.")
    if not getattr(settings, "TTS_ALLOW_CLOUD", False):
        print("ElevenLabs TTS is disabled. Using local German voice.")
        return local
    if not _has_cloud_credentials(settings):
        print("ElevenLabs key or voice ID is missing. Using local German voice.")
        return local
    return _create_elevenlabs(settings, local, diagnostics)


def _has_cloud_credentials(settings) -> bool:
    """Prüft Schlüssel und Stimmenkennung, ohne ihre Werte offenzulegen."""
    key = getattr(settings, "ELEVENLABS_API_KEY", "")
    voice_id = getattr(settings, "ELEVENLABS_VOICE_ID", "")
    return bool(key.strip() and voice_id.strip())


def _create_elevenlabs(
    settings,
    local: VectorSpeech,
    diagnostics: StructuredDiagnosticReporter | None = None,
) -> ElevenLabsSpeech:
    """Erzeugt den Cloud-TTS-Adapter mit begrenzter lokaler Rückfallstimme."""
    controls = ElevenLabsVoiceSettings(
        stability=settings.ELEVENLABS_STABILITY,
        similarity=settings.ELEVENLABS_SIMILARITY,
        style=settings.ELEVENLABS_STYLE,
        speed=settings.ELEVENLABS_SPEED,
    )
    return ElevenLabsSpeech(
        local,
        settings.ELEVENLABS_API_KEY,
        settings.ELEVENLABS_VOICE_ID,
        settings.ELEVENLABS_MODEL,
        settings.ELEVENLABS_TIMEOUT,
        controls,
        diagnostics=diagnostics,
    )
