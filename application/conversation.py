"""Console and WirePod conversation loops."""

import time
from dataclasses import dataclass
from functools import partial

from application.commands import CommandResult, ConsoleCommandHandler
from application.connection_supervisor import ConnectionSupervisor
from application.contextual_tool_conversation import (
    ControlledContextualToolConversation,
)
from application.controlled_turn_delivery import (
    handle_contextual_tool_turn,
    handle_expression_turn,
    handle_tool_turn,
)
from application.expression_conversation import ControlledExpressionConversation
from application.expression_delivery import ExpressionResponseCoordinator
from application.memory_conversation import (
    MEMORY_TOOL_NAME,
    ControlledMemoryConversation,
)
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
)
from application.voice_recovery import VoiceRecovery
from application.voice_turn_loop import VoiceTurnCallbacks, run_voice_turns
from brain.agent import Agent
from brain.expression_actions import ExpressionActionMapper
from diagnostics.events import StructuredDiagnosticReporter
from diagnostics.response_latency import ResponseLatencyTrace
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
    "'Schlage eine passende Aktion vor: Ich denke nach'. Local memory: "
    "'Erinnerung speichern: ...'."
)
@dataclass(frozen=True)
class _ConversationControllers:
    memory: ControlledMemoryConversation | None
    tools: ControlledToolConversation | None
    expression: ControlledExpressionConversation | None
    contextual: ControlledContextualToolConversation | None

    @property
    def awaiting_confirmation(self) -> bool:
        """Meldet eine offene Ja-Nein-Entscheidung eines Controllers."""
        return any(
            controller is not None and controller.awaiting_confirmation
            for controller in (
                self.memory,
                self.tools,
                self.expression,
                self.contextual,
            )
        )

    def cancel_pending(self) -> None:
        """Verwirft alle optional offenen Aktionen ohne Ausführung."""
        _cancel_pending(
            self.memory,
            self.tools,
            self.expression,
            self.contextual,
        )


def run_conversation(
    agent: Agent,
    speech: VectorSpeech,
    diagnostics: StructuredDiagnosticReporter | None = None,
) -> None:
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
            _handle_user_turn(agent, speech, controllers, user_text, diagnostics)
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
    conversation_follow_up: bool = True,
    diagnostics: StructuredDiagnosticReporter | None = None,
) -> None:
    """Führt eine private WirePod-Unterhaltung bis zum Abbruch oder Turnlimit aus."""
    _print_voice_intro()
    controllers = _create_conversation_controllers(agent, speech)
    recovery = _create_voice_recovery(connections, speech)
    follow_up_window = VoiceFollowUpWindow(follow_up, follow_up_timeout)
    callbacks = _create_voice_turn_callbacks(
        agent,
        speech,
        listener,
        controllers,
        diagnostics,
    )
    _run_voice_session(
        listener,
        callbacks,
        controllers,
        recovery,
        follow_up_window,
        listen_timeout,
        max_turns,
        conversation_follow_up,
    )


def _run_voice_session(
    listener: WirePodTranscriptListener,
    callbacks: VoiceTurnCallbacks,
    controllers: _ConversationControllers,
    recovery: VoiceRecovery,
    follow_up: VoiceFollowUpWindow,
    listen_timeout: float,
    max_turns: int | None,
    conversation_follow_up: bool,
) -> None:
    """Hält Initialisierung, Abbruch und Ressourcenfreigabe zusammen."""
    try:
        if not _prime_voice_listener(listener, recovery):
            return
        run_voice_turns(
            callbacks,
            follow_up,
            recovery,
            listen_timeout,
            max_turns,
            conversation_follow_up,
        )
    except KeyboardInterrupt:
        print("\nConversation ended.")
    finally:
        controllers.cancel_pending()
        follow_up.close()


def _create_voice_turn_callbacks(
    agent: Agent,
    speech: VectorSpeech,
    listener: WirePodTranscriptListener,
    controllers: _ConversationControllers,
    diagnostics: StructuredDiagnosticReporter | None = None,
) -> VoiceTurnCallbacks:
    """Bindet den Voice-Loop an Listener, Agent und sichere Dialogcontroller."""
    return VoiceTurnCallbacks(
        partial(_listen_for_user_text, listener),
        partial(
            _handle_user_turn,
            agent,
            speech,
            controllers,
            diagnostics=diagnostics,
        ),
        lambda: controllers.awaiting_confirmation,
        controllers.cancel_pending,
        partial(_acknowledge_follow_up_end, speech),
    )


def _acknowledge_follow_up_end(speech: VectorSpeech) -> None:
    """Bestätigt das lokale Gesprächsende einmalig ohne Modellaufruf."""
    message = "Gern."
    print(f"Vector: {message}")
    _speak_answer(speech, message)


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


def _print_voice_intro() -> None:
    """Zeigt die lokalen Hinweise für den WirePod-Sprachmodus an."""
    print("\nWirePod voice conversation started.")
    print("Say 'Hey Vector' followed by your question.")
    print("Controlled movements require a separate spoken yes.")
    print("Say 'Mit Ausdruck' for confirmed head and eye expression.")
    print("Say 'Schlage eine passende Aktion vor' for a reviewed suggestion.")
    print("Say 'Erinnerung speichern: ...' for confirmed local memory.")
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
        _create_memory_conversation(agent),
        _create_tool_conversation(agent),
        _create_expression_conversation(agent, speech),
        _create_contextual_tool_conversation(agent),
    )


def _create_memory_conversation(
    agent: Agent,
) -> ControlledMemoryConversation | None:
    """Erzeugt den Merkdialog nur mit registriertem lokalen Schreibwerkzeug."""
    registry = getattr(agent, "tool_registry", None)
    if not isinstance(registry, ToolRegistry):
        return None
    if MEMORY_TOOL_NAME not in {item.name for item in registry.definitions()}:
        return None
    return ControlledMemoryConversation(agent)


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
    diagnostics: StructuredDiagnosticReporter | None = None,
) -> bool:
    """Leitet einen Nutzerturn geordnet durch Befehle und Dialoggrenzen."""
    trace = ResponseLatencyTrace(diagnostics)
    if handle_tool_turn(controllers.tools, speech, user_text, trace):
        _cancel_pending(
            controllers.memory,
            controllers.expression,
            controllers.contextual,
        )
        return False
    if handle_tool_turn(controllers.memory, speech, user_text, trace):
        _cancel_pending(
            controllers.expression,
            controllers.contextual,
        )
        return False
    if handle_expression_turn(controllers.expression, speech, user_text, trace):
        _cancel_pending(controllers.contextual)
        return False
    if handle_contextual_tool_turn(
        controllers.contextual,
        speech,
        user_text,
        trace,
    ):
        _cancel_pending(controllers.expression)
        return False
    return respond_and_speak(agent, speech, user_text, trace)


def _cancel_pending(*controllers) -> None:
    """Verwirft offene Zustände aller vorhandenen Dialogcontroller."""
    for controller in controllers:
        if controller is not None:
            controller.cancel_pending()
