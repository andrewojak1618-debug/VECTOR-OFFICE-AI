"""Mediate selected tools, confirmations, and safe conversational messages."""

from dataclasses import dataclass
from enum import Enum

from application.confirmation import (
    ConfirmationDecision,
    classify_confirmation,
)
from brain.agent import Agent
from tools.permissions import PermissionLevel, ToolAuthorization
from tools.registry import ToolExecutionResult
from tools.selection import (
    ToolIntentSelector,
    ToolSelection,
    ToolSelectionStatus,
)


EMERGENCY_TOOL_NAME = "vector.emergency_stop"
SPOKEN_RESULT_TOOLS = frozenset({
    "development.latest_change",
    "research.python_latest_version",
    "research.python_source_status",
    "development.code_quality_status",
    "development.documentation_status",
    "development.project_document_catalog",
    "development.open_project_document",
    "memory.local_status",
    "knowledge.library_status",
    "system.local_service_status",
    "development.run_core_tests",
    "development.project_status",
    "development.next_roadmap_item",
    "office.local_datetime",
})


class ToolTurnStatus(Enum):
    """Describe how a tool-related conversation turn was handled."""

    NOT_HANDLED = "not_handled"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(frozen=True)
class ToolTurnResult:
    """Return a safe user-facing result for one controlled tool turn."""

    status: ToolTurnStatus
    message: str = ""
    speak: bool = False
    execution: ToolExecutionResult | None = None

    @property
    def handled(self) -> bool:
        """Meldet, ob dieser Turn zur kontrollierten Toolbehandlung gehört."""
        return self.status is not ToolTurnStatus.NOT_HANDLED


class ControlledToolConversation:
    """Keep one bounded pending proposal and execute only after authority."""

    def __init__(self, agent: Agent, selector: ToolIntentSelector):
        """Initialisiert den Tooldialog mit Agent und deterministischer Auswahl."""
        self.agent = agent
        self.selector = selector
        self._pending: ToolSelection | None = None

    @property
    def awaiting_confirmation(self) -> bool:
        """Meldet, ob ein kontrolliertes Tool auf eine Entscheidung wartet."""
        return self._pending is not None

    def cancel_pending(self) -> bool:
        """Verwirft eine offene Toolauswahl ohne Berechtigung oder Ausführung."""
        existed = self._pending is not None
        self._pending = None
        return existed

    def handle(self, user_text: str) -> ToolTurnResult:
        """Wählt, bestätigt, verwirft oder führt eine kontrollierte Toolanfrage aus."""
        selection = self.selector.select(user_text)
        if self._is_emergency(selection):
            self._pending = None
            return self._execute(
                selection,
                ToolAuthorization(allow_mutation=True),
                speak=False,
            )
        if self._pending is not None:
            return self._handle_confirmation(user_text)
        if selection.status is ToolSelectionStatus.NO_MATCH:
            return ToolTurnResult(ToolTurnStatus.NOT_HANDLED)
        if selection.status is ToolSelectionStatus.BLOCKED:
            return ToolTurnResult(ToolTurnStatus.BLOCKED, selection.message, True)
        if selection.permission is PermissionLevel.READ_ONLY:
            return self._execute(selection, None, speak=True)
        self._pending = selection
        return self._confirmation_result(selection)

    def _handle_confirmation(self, user_text: str) -> ToolTurnResult:
        """Verarbeitet eine separate Bestätigung oder Ablehnung des offenen Tools."""
        decision = classify_confirmation(user_text)
        pending = self._pending
        if decision in {
            ConfirmationDecision.REJECT,
            ConfirmationDecision.CANCEL,
        }:
            self.cancel_pending()
            return ToolTurnResult(
                ToolTurnStatus.CANCELLED,
                "Die Aktion wurde abgebrochen.",
                True,
            )
        if decision is not ConfirmationDecision.CONFIRM:
            return self._confirmation_result(pending)
        self._pending = None
        authority = _confirmed_authorization(pending.permission)
        return self._execute(pending, authority, speak=True)

    def _execute(
        self,
        selection: ToolSelection,
        authorization: ToolAuthorization | None,
        speak: bool,
    ) -> ToolTurnResult:
        """Führt eine geprüfte Toolauswahl aus und bereinigt das Dialogergebnis."""
        result = self.agent.execute_tool(
            selection.tool_name,
            selection.arguments,
            authorization,
        )
        if not result.succeeded:
            return ToolTurnResult(
                ToolTurnStatus.FAILED,
                "Die kontrollierte Aktion konnte nicht ausgeführt werden.",
                speak,
                result,
            )
        return ToolTurnResult(
            ToolTurnStatus.COMPLETED,
            _success_message(selection, result),
            speak,
            result,
        )

    @staticmethod
    def _is_emergency(selection: ToolSelection) -> bool:
        """Erkennt ausschließlich die feste Notfallstopp-Auswahl."""
        return (
            selection.status is ToolSelectionStatus.SELECTED
            and selection.tool_name == EMERGENCY_TOOL_NAME
        )

    @staticmethod
    def _confirmation_result(selection: ToolSelection) -> ToolTurnResult:
        """Erzeugt eine transparente Bestätigungsfrage passend zur Berechtigung."""
        if selection.permission is PermissionLevel.NETWORK:
            return ToolTurnResult(
                ToolTurnStatus.AWAITING_CONFIRMATION,
                "Dafür ist ein einmaliger Internetzugriff erforderlich. "
                f"Soll ich '{selection.label}' ausführen? Antworte mit Ja oder Nein.",
                True,
            )
        return ToolTurnResult(
            ToolTurnStatus.AWAITING_CONFIRMATION,
            f"Soll ich '{selection.label}' ausführen? Antworte mit Ja oder Nein.",
            True,
        )


def _confirmed_authorization(permission: PermissionLevel) -> ToolAuthorization:
    """Erzeugt eine einmalige Autorisierung exakt für die benötigte Berechtigung."""
    return ToolAuthorization(
        allow_mutation=permission in {
            PermissionLevel.MUTATING,
            PermissionLevel.DANGEROUS,
        },
        confirmed=True,
        allow_network=permission is PermissionLevel.NETWORK,
    )


def _success_message(
    selection: ToolSelection,
    result: ToolExecutionResult,
) -> str:
    """Wählt den begrenzten lokalen Erfolgstext für ein ausgeführtes Tool."""
    if selection.tool_name in SPOKEN_RESULT_TOOLS:
        return str(result.output["spoken_text"])
    if selection.tool_name == "vector.list_actions":
        return f"Sichere Aktionen: {result.output['actions']}."
    if selection.tool_name == EMERGENCY_TOOL_NAME:
        return "Der Notfallstopp wurde ausgeführt und verriegelt."
    return f"Die Aktion '{selection.label}' wurde ausgeführt."
