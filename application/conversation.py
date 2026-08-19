"""Console and WirePod conversation loops."""

import re
import time
from dataclasses import dataclass

from application.commands import CommandResult, ConsoleCommandHandler
from application.connection_supervisor import ConnectionSupervisor
from application.expression_conversation import ControlledExpressionConversation
from application.expression_delivery import (
    ExpressionResponseCoordinator,
    speech_style_for_cue,
)
from application.thinking import run_with_thinking
from application.tool_conversation import ControlledToolConversation
from application.voice_recovery import VoiceRecovery
from brain.agent import Agent
from brain.expression_actions import ExpressionActionMapper
from brain.providers import ProviderNotice
from tools.proposals import ToolProposalReviewer
from tools.registry import ToolRegistry
from tools.selection import ToolIntentSelector
from vector.speech import PreparedSpeech, SpeechStyle, VectorSpeech
from voice.wirepod_input import WirePodTranscriptListener


COMMAND_HELP = (
    "Commands: /remember, /feedback, /memories, /forget, /learn, "
    "/documents, /versions, /stale-vectors, /reindex, /reindex-all, "
    "/export-library, /export-memories, /forget-document, /clear, /exit"
)
TOOL_HELP = (
    "Controlled tools: 'Welche Aktionen kannst du?', 'Begrüße mich', "
    "'Schau nach oben', 'Lift nach oben', or 'Stopp sofort'. "
    "Movements require a separate yes. Expressive response: "
    "'Mit Ausdruck was bedeutet Freiheit'."
)
VOICE_EXIT_PHRASES = frozenset({
    "beende das gespräch",
    "bitte beenden",
    "dialog beenden",
    "gespräch abbrechen",
    "gespräch beenden",
    "programm beenden",
    "vector bitte beenden",
    "vector beenden",
    "vektor bitte beenden",
    "vektor beenden",
})
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


def _prepare_answer(agent: Agent, speech: VectorSpeech, user_text: str) -> _PreparedAnswer:
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
        return _speak_answer(speech, prepared.text, prepared.style)
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
        _speak_answer(speech, CLOUD_OFFLINE_NOTICE)
    elif notice is ProviderNotice.ALL_UNAVAILABLE:
        print(f"Vector: {PROVIDER_OFFLINE_NOTICE}")
        _speak_answer(speech, PROVIDER_OFFLINE_NOTICE)


def _speak_answer(
    speech: VectorSpeech,
    answer: str,
    style: SpeechStyle | None = None,
) -> bool:
    completed = speech.say(answer) if style is None else speech.say(answer, style)
    if completed:
        return True
    print("Vector could not play the response.")
    return False


def _response_speech_style(agent: Agent) -> SpeechStyle | None:
    emotional_state = getattr(agent, "emotional_state", None)
    state = getattr(emotional_state, "state", None)
    cue = getattr(state, "expression_cue", None)
    if cue is None:
        return None
    return speech_style_for_cue(cue)


def run_conversation(agent: Agent, speech: VectorSpeech) -> None:
    """Run the interactive console conversation until the user exits."""
    print("\nConversation started.")
    print(COMMAND_HELP)
    print(TOOL_HELP)
    command_handler = ConsoleCommandHandler(agent)
    tool_conversation = _create_tool_conversation(agent)
    expression_conversation = _create_expression_conversation(agent, speech)
    while True:
        user_text = _read_console_input()
        if user_text is None:
            return
        if not user_text:
            continue
        result = command_handler.handle(user_text)
        if result is CommandResult.EXIT:
            return
        if result is CommandResult.NOT_HANDLED:
            _handle_user_turn(
                agent,
                speech,
                tool_conversation,
                expression_conversation,
                user_text,
            )
        elif expression_conversation is not None:
            expression_conversation.cancel_pending()


def _read_console_input() -> str | None:
    print()
    try:
        return input("Du: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nConversation ended.")
        return None


def run_voice_conversation(
    agent: Agent,
    speech: VectorSpeech,
    listener: WirePodTranscriptListener,
    listen_timeout: float = 120.0,
    max_turns: int | None = None,
    connections: ConnectionSupervisor | None = None,
) -> None:
    """Run a private WirePod conversation until exit or the turn limit."""
    _print_voice_intro()
    tool_conversation = _create_tool_conversation(agent)
    expression_conversation = _create_expression_conversation(agent, speech)
    recovery = VoiceRecovery(
        connections,
        lambda answer: _speak_answer(speech, answer),
        sleeper=time.sleep,
    )
    try:
        if not _prime_voice_listener(listener, recovery):
            return
        _run_voice_turns(
            agent,
            speech,
            listener,
            tool_conversation,
            expression_conversation,
            listen_timeout,
            max_turns,
            recovery,
        )
    except KeyboardInterrupt:
        print("\nConversation ended.")
    finally:
        if expression_conversation is not None:
            expression_conversation.cancel_pending()


def _run_voice_turns(
    agent: Agent,
    speech: VectorSpeech,
    listener: WirePodTranscriptListener,
    tool_conversation: ControlledToolConversation | None,
    expression_conversation: ControlledExpressionConversation | None,
    listen_timeout: float,
    max_turns: int | None,
    recovery: VoiceRecovery,
) -> None:
    completed_turns = 0
    failures = 0
    while max_turns is None or completed_turns < max_turns:
        try:
            user_text = _listen_for_user_text(listener, listen_timeout)
        except RuntimeError:
            failures += 1
            if not recovery.retry_failure(failures):
                return
            continue
        recovery.complete()
        failures = 0
        if user_text is None:
            continue
        if _is_voice_exit_signal(user_text):
            print("Conversation ended.")
            return
        _handle_user_turn(
            agent,
            speech,
            tool_conversation,
            expression_conversation,
            user_text,
        )
        completed_turns += 1


def _prime_voice_listener(
    listener: WirePodTranscriptListener,
    recovery: VoiceRecovery,
) -> bool:
    for attempt in range(1, recovery.max_failures + 1):
        try:
            listener.prime()
            recovery.complete()
            return True
        except RuntimeError:
            if not recovery.retry_failure(attempt):
                return False
    return False


def _is_voice_exit_signal(user_text: str) -> bool:
    normalized = " ".join(user_text.casefold().strip().split())
    normalized = re.sub(r"[.!?,;:]+$", "", normalized).strip()
    return normalized in VOICE_EXIT_PHRASES


def _print_voice_intro() -> None:
    print("\nWirePod voice conversation started.")
    print("Say 'Hey Vector' followed by your question.")
    print("Controlled movements require a separate spoken yes.")
    print("Say 'Mit Ausdruck' for confirmed head and eye expression.")
    print("Say 'Vector beenden' to end the session.")


def _listen_for_user_text(
    listener: WirePodTranscriptListener,
    listen_timeout: float,
) -> str | None:
    print("\nListening...")
    event = listener.wait_for_transcript(listen_timeout)
    if event is None:
        print("No speech recognized before the timeout.")
        return None
    user_text = event.text.strip()
    print(f"Du: {user_text}")
    return user_text


def _create_tool_conversation(
    agent: Agent,
) -> ControlledToolConversation | None:
    registry = getattr(agent, "tool_registry", None)
    if not isinstance(registry, ToolRegistry):
        return None
    return ControlledToolConversation(agent, ToolIntentSelector(registry))


def _create_expression_conversation(
    agent: Agent,
    speech: VectorSpeech,
) -> ControlledExpressionConversation | None:
    registry = getattr(agent, "tool_registry", None)
    if not isinstance(registry, ToolRegistry):
        return None
    reviewer = ToolProposalReviewer(registry)
    mapper = ExpressionActionMapper(reviewer)
    coordinator = ExpressionResponseCoordinator(registry, speech)
    return ControlledExpressionConversation(agent, mapper, coordinator)


def _handle_user_turn(
    agent: Agent,
    speech: VectorSpeech,
    tool_controller: ControlledToolConversation | None,
    expression_controller: ControlledExpressionConversation | None,
    user_text: str,
) -> None:
    if _handle_tool_turn(tool_controller, speech, user_text):
        if expression_controller is not None:
            expression_controller.cancel_pending()
        return
    if _handle_expression_turn(expression_controller, speech, user_text):
        return
    respond_and_speak(agent, speech, user_text)


def _handle_tool_turn(
    controller: ControlledToolConversation | None,
    speech: VectorSpeech,
    user_text: str,
) -> bool:
    if controller is None:
        return False
    result = controller.handle(user_text)
    if not result.handled:
        return False
    if result.message:
        print(f"Vector: {result.message}")
    if result.speak and result.message:
        _speak_answer(speech, result.message)
    return True


def _handle_expression_turn(
    controller: ControlledExpressionConversation | None,
    speech: VectorSpeech,
    user_text: str,
) -> bool:
    if controller is None:
        return False
    result = controller.handle(user_text)
    if not result.handled:
        return False
    if result.message:
        print(f"Vector: {result.message}")
    if result.speak and result.message:
        _speak_answer(speech, result.message)
    if result.delivery is not None and not result.delivery.speech_completed:
        print("Vector could not play the prepared response.")
    return True
