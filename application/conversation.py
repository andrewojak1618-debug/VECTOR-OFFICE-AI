"""Console and WirePod conversation loops."""

from brain.agent import Agent
from tools.registry import ToolRegistry
from tools.selection import ToolIntentSelector
from vector.speech import VectorSpeech
from voice.wirepod_input import WirePodTranscriptListener

from application.commands import CommandResult, ConsoleCommandHandler
from application.expression_conversation import ControlledExpressionConversation
from application.expression_delivery import ExpressionResponseCoordinator
from application.tool_conversation import ControlledToolConversation
from brain.expression_actions import ExpressionActionMapper
from tools.proposals import ToolProposalReviewer


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
VOICE_EXIT_PHRASES = {
    "gespräch beenden",
    "programm beenden",
    "vector beenden",
    "vektor beenden",
}


def respond_and_speak(
    agent: Agent,
    speech: VectorSpeech,
    user_text: str,
) -> bool:
    """Generate one answer and play it through Vector."""
    print("Thinking...")
    try:
        answer = agent.respond(user_text)
    except (RuntimeError, ValueError) as exc:
        print(f"Brain request failed: {exc}")
        return False
    print(f"Vector: {answer}")
    return _speak_answer(speech, answer)


def _speak_answer(speech: VectorSpeech, answer: str) -> bool:
    if speech.say(answer):
        return True
    print("Vector could not play the response.")
    return False


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
) -> None:
    """Run a private WirePod conversation until exit or the turn limit."""
    _print_voice_intro()
    listener.prime()
    tool_conversation = _create_tool_conversation(agent)
    expression_conversation = _create_expression_conversation(agent, speech)
    completed_turns = 0
    while max_turns is None or completed_turns < max_turns:
        try:
            user_text = _listen_for_user_text(listener, listen_timeout)
        except KeyboardInterrupt:
            print("\nConversation ended.")
            return
        except RuntimeError as exc:
            print(f"Voice input failed: {exc}")
            return
        if user_text is None:
            continue
        if user_text.casefold() in VOICE_EXIT_PHRASES:
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
