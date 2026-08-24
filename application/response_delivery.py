"""Prepare model answers and deliver provider notices plus spoken audio."""

from dataclasses import dataclass

from application.expression_delivery import speech_style_for_cue
from application.thinking import run_with_thinking
from brain.agent import Agent
from brain.providers import ProviderNotice
from brain.response_quality import (
    SAFE_PROVIDER_REPLACEMENT,
    ProviderResponseValidationError,
    safe_spoken_response,
)
from vector.speech import (
    PreparedSpeech,
    SpeechProviderNotice,
    SpeechStyle,
    VectorSpeech,
)


CLOUD_OFFLINE_NOTICE = (
    "Ich kann das Kollektiv gerade nicht erreichen. "
    "Ich arbeite vorübergehend lokal weiter."
)
PROVIDER_OFFLINE_NOTICE = (
    "Ich kann das Kollektiv gerade nicht erreichen. "
    "Offenbar besteht ein Verbindungsproblem."
)
TTS_OFFLINE_NOTICE = (
    "Meine Cloud-Stimme ist gerade nicht erreichbar. "
    "Ich spreche vorübergehend lokal weiter."
)
PROVIDER_RECOVERY_NOTICE = "Die unterbrochene Verbindung ist wiederhergestellt."
VECTOR_UNAVAILABLE_MESSAGE = (
    "Vector ist gerade nicht erreichbar. Die Unterhaltung bleibt aktiv."
)


@dataclass(frozen=True)
class _PreparedAnswer:
    text: str
    style: SpeechStyle | None
    audio: PreparedSpeech | None


def respond_and_speak(
    agent: Agent,
    speech: VectorSpeech,
    user_text: str,
) -> bool:
    """Erzeugt eine Antwort und gibt sie über Vector wieder."""
    print("Thinking...")
    try:
        prepared = run_with_thinking(
            lambda: _prepare_answer(agent, speech, user_text),
            speech,
        )
    except ProviderResponseValidationError:
        _speak_provider_notice(agent, speech)
        print(f"Vector: {SAFE_PROVIDER_REPLACEMENT}")
        return speak_answer(speech, SAFE_PROVIDER_REPLACEMENT)
    except (RuntimeError, ValueError) as exc:
        _speak_provider_notice(agent, speech)
        print(f"Brain request failed: {exc}")
        return False
    print(f"Vector: {prepared.text}")
    _speak_provider_notice(agent, speech)
    return _play_answer(speech, prepared)


def speak_answer(
    speech: VectorSpeech,
    answer: str,
    style: SpeechStyle | None = None,
) -> bool:
    """Spricht eine Antwort und meldet Wiedergabefehler ohne sensible Details."""
    spoken_text = safe_spoken_response(answer)
    try:
        completed = (
            speech.say(spoken_text)
            if style is None
            else speech.say(spoken_text, style)
        )
    except (OSError, RuntimeError, TypeError, ValueError):
        completed = False
    if completed:
        return True
    print(VECTOR_UNAVAILABLE_MESSAGE)
    return False


def _prepare_answer(
    agent: Agent,
    speech: VectorSpeech,
    user_text: str,
) -> _PreparedAnswer:
    """Erzeugt Antwort, Sprachstil und nach Möglichkeit vorbereitetes Audio."""
    answer = agent.respond(user_text)
    style = _response_speech_style(agent)
    prepare = getattr(speech, "prepare", None)
    if not callable(prepare):
        return _PreparedAnswer(answer, style, None)
    selected = style or SpeechStyle.CONVERSATIONAL
    try:
        audio = prepare(answer, selected)
    except (OSError, RuntimeError, TypeError, ValueError):
        audio = None
    return _PreparedAnswer(answer, style, audio)


def _play_answer(speech: VectorSpeech, prepared: _PreparedAnswer) -> bool:
    """Spielt vorbereitetes Audio oder kontrolliert die direkte Sprachausgabe ab."""
    if prepared.audio is None:
        return speak_answer(speech, prepared.text, prepared.style)
    try:
        completed = bool(speech.play_prepared(prepared.audio))
    except (OSError, RuntimeError, TypeError, ValueError):
        prepared.audio.close()
        completed = False
    if not completed:
        print(VECTOR_UNAVAILABLE_MESSAGE)
    return completed


def _speak_provider_notice(agent: Agent, speech: VectorSpeech) -> None:
    """Spricht höchstens einen priorisierten Hinweis je Providerübergang."""
    language_model = getattr(agent, "language_model", None)
    model_notice = _consume_notice(language_model)
    speech_notice = _consume_notice(speech)
    message = _provider_notice_message(model_notice, speech_notice)
    if message is None:
        return
    print(f"Vector: {message}")
    local_speech = getattr(speech, "local_speech", speech)
    speak_answer(local_speech, message)


def _consume_notice(provider) -> object | None:
    """Verbraucht einen optionalen Providerhinweis ohne konkrete Anbieterkopplung."""
    consume = getattr(provider, "consume_notice", None)
    return consume() if callable(consume) else None


def _provider_notice_message(model_notice, speech_notice) -> str | None:
    """Wählt aus gleichzeitigen Zustandswechseln genau eine Meldung."""
    if model_notice is ProviderNotice.ALL_UNAVAILABLE:
        return PROVIDER_OFFLINE_NOTICE
    if model_notice is ProviderNotice.LOCAL_FALLBACK:
        return CLOUD_OFFLINE_NOTICE
    if speech_notice is SpeechProviderNotice.LOCAL_FALLBACK:
        return TTS_OFFLINE_NOTICE
    recovered = (
        model_notice is ProviderNotice.PRIMARY_RECOVERED
        or speech_notice is SpeechProviderNotice.CLOUD_RECOVERED
    )
    return PROVIDER_RECOVERY_NOTICE if recovered else None


def _response_speech_style(agent: Agent) -> SpeechStyle | None:
    """Leitet den Sprachstil aus dem aktuellen kontrollierten Ausdruckszustand ab."""
    emotional_state = getattr(agent, "emotional_state", None)
    state = getattr(emotional_state, "state", None)
    cue = getattr(state, "expression_cue", None)
    if cue is None:
        return None
    return speech_style_for_cue(cue)
