"""Wählt den freigegebenen lokalen Provider für kurze Folgeantworten."""

from application.voice_followup import FollowUpCapture
from voice.vosk_followup import VoskFollowUpCapture
from voice.windows_followup import WindowsSpeechFollowUpCapture


SUPPORTED_FOLLOW_UP_PROVIDERS = frozenset({"vosk", "windows"})


def create_follow_up_capture(settings) -> FollowUpCapture | None:
    """Erzeugt und erwärmt genau den konfigurierten lokalen Aufnahmeweg."""
    if not getattr(settings, "VOICE_FOLLOWUP_LOCAL", True):
        return None
    provider = _provider_name(settings)
    capture = _build_capture(provider, settings)
    capture.prepare()
    return capture


def _provider_name(settings) -> str:
    """Normalisiert den Providernamen und blockiert unbekannte Aufnahmewege."""
    provider = str(
        getattr(settings, "VOICE_FOLLOWUP_PROVIDER", "vosk"),
    ).casefold().strip()
    if provider not in SUPPORTED_FOLLOW_UP_PROVIDERS:
        raise ValueError("VOICE_FOLLOWUP_PROVIDER must be 'vosk' or 'windows'.")
    return provider


def _build_capture(provider: str, settings) -> FollowUpCapture:
    """Baut den ausgewählten Adapter mit gemeinsamen Sicherheitsgrenzen."""
    confidence = getattr(settings, "VOICE_FOLLOWUP_MIN_CONFIDENCE", 0.15)
    if provider == "windows":
        return WindowsSpeechFollowUpCapture(min_confidence=confidence)
    device = str(getattr(settings, "VOSK_AUDIO_DEVICE", "")).strip() or None
    return VoskFollowUpCapture(
        getattr(settings, "VOSK_MODEL_PATH", ""),
        min_confidence=confidence,
        audio_device=device,
    )
