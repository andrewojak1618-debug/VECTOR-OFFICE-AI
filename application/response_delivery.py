"""Prepare model answers and deliver provider notices plus spoken audio."""

from dataclasses import dataclass

from application.expression_delivery import speech_style_for_cue
from application.thinking import run_with_thinking
from brain.agent import Agent
from brain.providers import ProviderNotice
from vector.speech import PreparedSpeech, SpeechStyle, VectorSpeech


CLOUD_OFFLINE_NOTICE = (
    "Ich kann das Kollektiv gerade nicht erreichen. "
    "Ich arbeite vorübergehend lokal weiter."
)
PROVIDER_OFFLINE_NOTICE = (
    "Ich kann das Kollektiv gerade nicht erreichen. "
    "Offenbar besteht ein Verbindungsproblem."
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
    """Generate one answer and play it through Vector."""
    print("Thinking...")
    try:
        prepared = run_with_thinking(
            lambda: _prepare_answer(agent, speech, user_text),
            speech,
        )
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
    """Speak one answer and report a sanitized playback failure."""
    completed = speech.say(answer) if style is None else speech.say(answer, style)
    if completed:
        return True
    print("Vector could not play the response.")
    return False


def _prepare_answer(
    agent: Agent,
    speech: VectorSpeech,
    user_text: str,
) -> _PreparedAnswer:
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
    if prepared.audio is None:
        return speak_answer(speech, prepared.text, prepared.style)
    try:
        completed = bool(speech.play_prepared(prepared.audio))
    except (OSError, RuntimeError, TypeError, ValueError):
        prepared.audio.close()
        completed = False
    if not completed:
        print("Vector could not play the response.")
    return completed


def _speak_provider_notice(agent: Agent, speech: VectorSpeech) -> None:
    language_model = getattr(agent, "language_model", None)
    consume = getattr(language_model, "consume_notice", None)
    if not callable(consume):
        return
    notice = consume()
    if notice is ProviderNotice.LOCAL_FALLBACK:
        print(f"Vector: {CLOUD_OFFLINE_NOTICE}")
        speak_answer(speech, CLOUD_OFFLINE_NOTICE)
    elif notice is ProviderNotice.ALL_UNAVAILABLE:
        print(f"Vector: {PROVIDER_OFFLINE_NOTICE}")
        speak_answer(speech, PROVIDER_OFFLINE_NOTICE)


def _response_speech_style(agent: Agent) -> SpeechStyle | None:
    emotional_state = getattr(agent, "emotional_state", None)
    state = getattr(emotional_state, "state", None)
    cue = getattr(state, "expression_cue", None)
    if cue is None:
        return None
    return speech_style_for_cue(cue)
