"""Console and WirePod conversation loops."""

import re
import time
from dataclasses import dataclass
from functools import partial

from application.commands import CommandResult, ConsoleCommandHandler
from application.connection_supervisor import ConnectionSupervisor
from application.contextual_tool_conversation import (
    ControlledContextualToolConversation,
)
from application.expression_conversation import ControlledExpressionConversation
from application.expression_delivery import ExpressionResponseCoordinator
from application.model_tool_proposals import ModelToolProposalService
from application.response_delivery import (
    CLOUD_OFFLINE_NOTICE,
    PROVIDER_OFFLINE_NOTICE,
    respond_and_speak,
    speak_answer as _speak_answer,
)
from application.tool_conversation import ControlledToolConversation
from application.voice_followup import (
    FollowUpCapture,
    VoiceFollowUpWindow,
    receive_voice_turn,
)
from application.voice_recovery import VoiceRecovery
from brain.agent import Agent
from brain.expression_actions import ExpressionActionMapper
from tools.proposals import (
    CONTEXTUAL_EXPRESSION_PROPOSAL_OPTIONS,
    ToolProposalReviewer,
)
from tools.registry import ToolRegistry
from tools.selection import ToolIntentSelector
from vector.speech import VectorSpeech
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
    "'Mit Ausdruck was bedeutet Freiheit'. Contextual suggestion: "
    "'Schlage eine passende Aktion vor: Ich denke nach'."
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


@dataclass(frozen=True)
class _ConversationControllers:
    tools: ControlledToolConversation | None
    expression: ControlledExpressionConversation | None
    contextual: ControlledContextualToolConversation | None

    @property
    def awaiting_confirmation(self) -> bool:
        """Meldet eine offene Ja-Nein-Entscheidung eines Controllers."""
        return any(
            controller is not None and controller.awaiting_confirmation
            for controller in (self.tools, self.expression, self.contextual)
        )

    def cancel_pending(self) -> None:
        """Verwirft alle optional offenen Aktionen ohne Ausführung."""
        _cancel_pending(self.tools, self.expression, self.contextual)


def run_conversation(agent: Agent, speech: VectorSpeech) -> None:
    """Führt die interaktive Konsolenunterhaltung bis zum Nutzerabbruch aus."""
    print("\nConversation started.")
    print(COMMAND_HELP)
    print(TOOL_HELP)
    command_handler = ConsoleCommandHandler(agent)
    controllers = _create_conversation_controllers(agent, speech)
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
            _handle_user_turn(agent, speech, controllers, user_text)
        else:
            controllers.cancel_pending()


def _read_console_input() -> str | None:
    """Liest eine Konsoleneingabe und behandelt Dateiende als Sitzungsende."""
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
    follow_up: FollowUpCapture | None = None,
    follow_up_timeout: float = 5.0,
) -> None:
    """Führt eine private WirePod-Unterhaltung bis zum Abbruch oder Turnlimit aus."""
    _print_voice_intro()
    controllers = _create_conversation_controllers(agent, speech)
    recovery = _create_voice_recovery(connections, speech)
    follow_up_window = VoiceFollowUpWindow(follow_up, follow_up_timeout)
    try:
        if not _prime_voice_listener(listener, recovery):
            return
        _run_voice_turns(
            agent,
            speech,
            listener,
            controllers,
            listen_timeout,
            max_turns,
            recovery,
            follow_up_window,
        )
    except KeyboardInterrupt:
        print("\nConversation ended.")
    finally:
        controllers.cancel_pending()


def _run_voice_turns(
    agent: Agent,
    speech: VectorSpeech,
    listener: WirePodTranscriptListener,
    controllers: _ConversationControllers,
    listen_timeout: float,
    max_turns: int | None,
    recovery: VoiceRecovery,
    follow_up: VoiceFollowUpWindow,
) -> None:
    """Verarbeitet begrenzt aufeinanderfolgende Spracheingaben und Wiederholungen."""
    completed_turns = 0
    failures = 0
    listen = partial(_listen_for_user_text, listener)
    while max_turns is None or completed_turns < max_turns:
        user_text, failures, keep_running = receive_voice_turn(
            listen,
            follow_up,
            recovery,
            controllers.cancel_pending,
            listen_timeout,
            failures,
        )
        if not keep_running:
            return
        if user_text is None:
            continue
        follow_up.consume_transcript()
        if _is_voice_exit_signal(user_text):
            print("Conversation ended.")
            return
        _handle_user_turn(agent, speech, controllers, user_text)
        completed_turns += 1
        if follow_up.update(controllers.awaiting_confirmation):
            print("Listening for a confirmation without another wakeword...")


def _create_voice_recovery(
    connections: ConnectionSupervisor | None,
    speech: VectorSpeech,
) -> VoiceRecovery:
    """Erzeugt die begrenzte Wiederherstellung für den WirePod-Dialog."""
    return VoiceRecovery(
        connections,
        lambda answer: _speak_answer(speech, answer),
        sleeper=time.sleep,
    )


def _prime_voice_listener(
    listener: WirePodTranscriptListener,
    recovery: VoiceRecovery,
) -> bool:
    """Initialisiert den Listener und meldet Startfehler ohne Gesprächsdaten."""
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
    """Erkennt feste gesprochene Signale zum kontrollierten Sitzungsende."""
    normalized = " ".join(user_text.casefold().strip().split())
    normalized = re.sub(r"[.!?,;:]+$", "", normalized).strip()
    return normalized in VOICE_EXIT_PHRASES


def _print_voice_intro() -> None:
    """Zeigt die lokalen Hinweise für den WirePod-Sprachmodus an."""
    print("\nWirePod voice conversation started.")
    print("Say 'Hey Vector' followed by your question.")
    print("Controlled movements require a separate spoken yes.")
    print("Say 'Mit Ausdruck' for confirmed head and eye expression.")
    print("Say 'Schlage eine passende Aktion vor' for a reviewed suggestion.")
    print("Say 'Vector beenden' to end the session.")


def _listen_for_user_text(
    listener: WirePodTranscriptListener,
    listen_timeout: float,
) -> str | None:
    """Wartet begrenzt auf eine eindeutige neue WirePod-Transkription."""
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
    """Erzeugt den deterministischen, Registry-gebundenen Tooldialog."""
    registry = getattr(agent, "tool_registry", None)
    if not isinstance(registry, ToolRegistry):
        return None
    return ControlledToolConversation(agent, ToolIntentSelector(registry))


def _create_conversation_controllers(
    agent: Agent,
    speech: VectorSpeech,
) -> _ConversationControllers:
    """Setzt die optionalen Tool- und Ausdruckscontroller einer Sitzung zusammen."""
    return _ConversationControllers(
        _create_tool_conversation(agent),
        _create_expression_conversation(agent, speech),
        _create_contextual_tool_conversation(agent),
    )


def _create_expression_conversation(
    agent: Agent,
    speech: VectorSpeech,
) -> ControlledExpressionConversation | None:
    """Erzeugt den Ausdrucksdialog nur bei verfügbaren Aktionswerkzeugen."""
    registry = getattr(agent, "tool_registry", None)
    if not isinstance(registry, ToolRegistry):
        return None
    reviewer = ToolProposalReviewer(registry)
    mapper = ExpressionActionMapper(reviewer)
    coordinator = ExpressionResponseCoordinator(registry, speech)
    return ControlledExpressionConversation(agent, mapper, coordinator)


def _create_contextual_tool_conversation(
    agent: Agent,
) -> ControlledContextualToolConversation | None:
    """Erzeugt den Kontextvorschlagsdialog nur bei freigegebenem Profil."""
    registry = getattr(agent, "tool_registry", None)
    language_model = getattr(agent, "language_model", None)
    if not isinstance(registry, ToolRegistry) or language_model is None:
        return None
    reviewer = ToolProposalReviewer(
        registry,
        CONTEXTUAL_EXPRESSION_PROPOSAL_OPTIONS,
    )
    service = ModelToolProposalService(language_model, reviewer)
    return ControlledContextualToolConversation(agent, service)


def _handle_user_turn(
    agent: Agent,
    speech: VectorSpeech,
    controllers: _ConversationControllers,
    user_text: str,
) -> None:
    """Leitet einen Nutzerturn geordnet durch Befehle und Dialoggrenzen."""
    if _handle_tool_turn(controllers.tools, speech, user_text):
        _cancel_pending(controllers.expression, controllers.contextual)
        return
    if _handle_expression_turn(controllers.expression, speech, user_text):
        _cancel_pending(controllers.contextual)
        return
    if _handle_contextual_tool_turn(controllers.contextual, speech, user_text):
        _cancel_pending(controllers.expression)
        return
    respond_and_speak(agent, speech, user_text)


def _handle_tool_turn(
    controller: ControlledToolConversation | None,
    speech: VectorSpeech,
    user_text: str,
) -> bool:
    """Verarbeitet einen kontrollierten Toolturn und spricht dessen Ergebnis."""
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
    """Verarbeitet einen bestätigten Ausdrucksturn samt sicherer Ausgabe."""
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


def _handle_contextual_tool_turn(
    controller: ControlledContextualToolConversation | None,
    speech: VectorSpeech,
    user_text: str,
) -> bool:
    """Verarbeitet einen geprüften kontextbezogenen Toolvorschlag."""
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


def _cancel_pending(*controllers) -> None:
    """Verwirft offene Zustände aller vorhandenen Dialogcontroller."""
    for controller in controllers:
        if controller is not None:
            controller.cancel_pending()
