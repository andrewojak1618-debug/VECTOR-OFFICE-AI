"""Mediate selected tools, confirmations, and safe conversational messages."""

from dataclasses import dataclass
from enum import Enum

from brain.agent import Agent
from tools.permissions import PermissionLevel, ToolAuthorization
from tools.registry import ToolExecutionResult
from tools.selection import (
    ToolIntentSelector,
    ToolSelection,
    ToolSelectionStatus,
)


EMERGENCY_TOOL_NAME = "vector.emergency_stop"
CONFIRMATION_PHRASES = frozenset({"ja", "ja bitte", "bestätigen", "ausführen"})
CANCELLATION_PHRASES = frozenset({
    "nein",
    "abbrechen",
    "abbruch",
    "nicht ausführen",
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
        """Report whether this turn belongs to controlled tool handling."""
        return self.status is not ToolTurnStatus.NOT_HANDLED


class ControlledToolConversation:
    """Keep one bounded pending proposal and execute only after authority."""

    def __init__(self, agent: Agent, selector: ToolIntentSelector):
        self.agent = agent
        self.selector = selector
        self._pending: ToolSelection | None = None

    def handle(self, user_text: str) -> ToolTurnResult:
        """Select, confirm, cancel, or execute one controlled tool request."""
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
        normalized = _normalize_confirmation(user_text)
        pending = self._pending
        if normalized in CANCELLATION_PHRASES:
            self._pending = None
            return ToolTurnResult(
                ToolTurnStatus.CANCELLED,
                "Die Aktion wurde abgebrochen.",
                True,
            )
        if normalized not in CONFIRMATION_PHRASES:
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
        return (
            selection.status is ToolSelectionStatus.SELECTED
            and selection.tool_name == EMERGENCY_TOOL_NAME
        )

    @staticmethod
    def _confirmation_result(selection: ToolSelection) -> ToolTurnResult:
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


def _normalize_confirmation(value: str) -> str:
    return " ".join(value.casefold().strip().rstrip(".!?").split())


def _confirmed_authorization(permission: PermissionLevel) -> ToolAuthorization:
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
    if selection.tool_name == "research.python_latest_version":
        return str(result.output["spoken_text"])
    if selection.tool_name == "research.python_source_status":
        return str(result.output["spoken_text"])
    if selection.tool_name == "development.documentation_status":
        return str(result.output["spoken_text"])
    if selection.tool_name == "memory.local_status":
        return str(result.output["spoken_text"])
    if selection.tool_name == "knowledge.library_status":
        return str(result.output["spoken_text"])
    if selection.tool_name == "system.local_service_status":
        return str(result.output["spoken_text"])
    if selection.tool_name == "development.run_core_tests":
        return str(result.output["spoken_text"])
    if selection.tool_name == "development.project_status":
        return str(result.output["spoken_text"])
    if selection.tool_name == "development.next_roadmap_item":
        return str(result.output["spoken_text"])
    if selection.tool_name == "office.local_datetime":
        return str(result.output["spoken_text"])
    if selection.tool_name == "vector.list_actions":
        return f"Sichere Aktionen: {result.output['actions']}."
    if selection.tool_name == EMERGENCY_TOOL_NAME:
        return "Der Notfallstopp wurde ausgeführt und verriegelt."
    return f"Die Aktion '{selection.label}' wurde ausgeführt."
