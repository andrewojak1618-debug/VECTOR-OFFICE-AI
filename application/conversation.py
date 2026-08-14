"""Console and WirePod conversation loops."""

from brain.agent import Agent
from vector.speech import VectorSpeech
from voice.wirepod_input import WirePodTranscriptListener

from application.commands import CommandResult, ConsoleCommandHandler


COMMAND_HELP = (
    "Commands: /remember, /memories, /forget, /learn, "
    "/documents, /forget-document, /clear, /exit"
)
VOICE_EXIT_PHRASES = {
    "gespräch beenden",
    "programm beenden",
    "vector beenden",
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
    command_handler = ConsoleCommandHandler(agent)
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
            respond_and_speak(agent, speech, user_text)


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
    completed_turns = 0
    while max_turns is None or completed_turns < max_turns:
        try:
            user_text = _listen_for_user_text(listener, listen_timeout)
        except RuntimeError as exc:
            print(f"Voice input failed: {exc}")
            return
        if user_text is None:
            continue
        if user_text.casefold() in VOICE_EXIT_PHRASES:
            print("Conversation ended.")
            return
        respond_and_speak(agent, speech, user_text)
        completed_turns += 1


def _print_voice_intro() -> None:
    print("\nWirePod voice conversation started.")
    print("Say 'Hey Vector' followed by your question.")
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
