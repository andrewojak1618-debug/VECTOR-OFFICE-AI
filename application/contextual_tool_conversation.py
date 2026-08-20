"""Activate reviewed contextual expression proposals after explicit consent."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from application.model_tool_proposals import ModelToolProposalService
from brain.agent import Agent
from tools.permissions import PermissionLevel, ToolAuthorization
from tools.proposals import ToolProposal, ToolProposalStatus
from tools.registry import ToolExecutionResult


DEFAULT_PROPOSAL_TTL_SECONDS = 30.0
PROPOSAL_REQUEST_PREFIXES = (
    "schlage eine passende aktion vor",
    "welche aktion passt dazu",
)
PROPOSAL_REQUEST_SEPARATORS = " \t:?!,;"
CONFIRMATION_PHRASES = frozenset({"ja", "ja bitte", "bestätigen", "ausführen"})
CANCELLATION_PHRASES = frozenset({
    "nein",
    "abbrechen",
    "abbruch",
    "nicht ausführen",
})
CONTEXTUAL_EXPRESSION_TARGETS = {
    "vector.reflective_expression": "reflective_expression",
}


class ContextualToolTurnStatus(Enum):
    """Classify one explicitly activated contextual proposal turn."""

    NOT_HANDLED = "not_handled"
    AWAITING_CONTEXT = "awaiting_context"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    NO_PROPOSAL = "no_proposal"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(frozen=True)
class ContextualToolTurnResult:
    """Return bounded user-facing state without retaining the request text."""

    status: ContextualToolTurnStatus
    message: str = ""
    speak: bool = False
    execution: ToolExecutionResult | None = None

    @property
    def handled(self) -> bool:
        """Report whether the turn belongs to contextual proposal handling."""
        return self.status is not ContextualToolTurnStatus.NOT_HANDLED


@dataclass(frozen=True)
class _PendingProposal:
    proposal_id: str
    label: str
    expires_at: float


class ControlledContextualToolConversation:
    """Hold one reviewed proposal until a separate bounded confirmation."""

    def __init__(
        self,
        agent: Agent,
        service: ModelToolProposalService,
        ttl_seconds: float = DEFAULT_PROPOSAL_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ):
        if not isinstance(agent, Agent):
            raise TypeError("Contextual tool conversation requires an Agent.")
        if not isinstance(service, ModelToolProposalService):
            raise TypeError("Contextual tool conversation requires a proposal service.")
        if not 5.0 <= ttl_seconds <= 120.0:
            raise ValueError("Contextual proposal TTL must be between 5 and 120 seconds.")
        if not callable(clock):
            raise TypeError("Contextual proposal clock must be callable.")
        self._agent = agent
        self._service = service
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._pending: _PendingProposal | None = None
        self._context_expires_at: float | None = None

    @property
    def awaiting_context(self) -> bool:
        """Report whether the next utterance supplies requested context."""
        return (
            self._context_expires_at is not None
            and self._clock() < self._context_expires_at
        )

    @property
    def awaiting_confirmation(self) -> bool:
        """Report whether one unexpired decision may still be confirmed."""
        return self._pending is not None and not self._has_expired()

    def cancel_pending(self) -> bool:
        """Discard one proposal without creating authority or execution."""
        existed = self._pending is not None or self._context_expires_at is not None
        self._pending = None
        self._context_expires_at = None
        return existed

    def handle(self, user_text: str) -> ContextualToolTurnResult:
        """Propose, confirm, cancel, expire, or reject one safe expression."""
        if not isinstance(user_text, str) or not user_text.strip():
            raise ValueError("Contextual tool input must not be empty.")
        if self._pending is not None:
            return self._handle_confirmation(user_text)
        if self._context_expires_at is not None:
            return self._handle_context(user_text)
        request = _extract_proposal_request(user_text)
        if request is None:
            return ContextualToolTurnResult(ContextualToolTurnStatus.NOT_HANDLED)
        if not request:
            self._context_expires_at = self._clock() + self._ttl_seconds
            return self._result(
                ContextualToolTurnStatus.AWAITING_CONTEXT,
                "Was soll ich dabei berücksichtigen? Nenne mir jetzt den Kontext.",
            )
        return self._prepare(request)

    def _handle_context(self, user_text: str) -> ContextualToolTurnResult:
        if self._clock() >= self._context_expires_at:
            self._context_expires_at = None
            return self._result(
                ContextualToolTurnStatus.EXPIRED,
                "Die Kontextanfrage ist abgelaufen und wurde verworfen.",
            )
        normalized = _normalize_choice(user_text)
        if normalized in CANCELLATION_PHRASES:
            self._context_expires_at = None
            return self._result(
                ContextualToolTurnStatus.CANCELLED,
                "Die Kontextanfrage wurde verworfen.",
            )
        self._context_expires_at = None
        return self._prepare(user_text.strip())

    def _prepare(self, request: str) -> ContextualToolTurnResult:
        try:
            review = self._service.propose(
                request,
                explicit_action_request=True,
            )
        except ValueError:
            return self._blocked_result()
        if review.status is ToolProposalStatus.NO_PROPOSAL:
            return self._result(
                ContextualToolTurnStatus.NO_PROPOSAL,
                "Ich sehe dafür keine passende freigegebene Ausdrucksaktion.",
            )
        proposal = review.proposal
        if not review.accepted or not self._is_allowed_expression(proposal):
            return self._blocked_result()
        self._pending = _PendingProposal(
            proposal.proposal_id,
            proposal.label,
            self._clock() + self._ttl_seconds,
        )
        return self._confirmation_result(self._pending)

    def _handle_confirmation(self, user_text: str) -> ContextualToolTurnResult:
        if self._has_expired():
            self._pending = None
            return self._result(
                ContextualToolTurnStatus.EXPIRED,
                "Der Aktionsvorschlag ist abgelaufen und wurde verworfen.",
            )
        normalized = _normalize_choice(user_text)
        if normalized in CANCELLATION_PHRASES:
            self._pending = None
            return self._result(
                ContextualToolTurnStatus.CANCELLED,
                "Der Aktionsvorschlag wurde verworfen.",
            )
        if normalized not in CONFIRMATION_PHRASES:
            return self._confirmation_result(self._pending)
        return self._execute_pending()

    def _execute_pending(self) -> ContextualToolTurnResult:
        pending = self._pending
        self._pending = None
        review = self._service.reviewer.resolve(pending.proposal_id)
        proposal = review.proposal
        if not review.accepted or not self._is_allowed_expression(proposal):
            return self._blocked_result()
        authority = ToolAuthorization(allow_mutation=True, confirmed=True)
        execution = self._agent.execute_tool(
            proposal.tool_name,
            proposal.arguments,
            authority,
        )
        if not execution.succeeded:
            return self._result(
                ContextualToolTurnStatus.FAILED,
                "Die bestätigte Ausdrucksaktion konnte nicht ausgeführt werden.",
                execution,
            )
        return self._result(
            ContextualToolTurnStatus.COMPLETED,
            f"Die Ausdrucksaktion '{proposal.label}' wurde ausgeführt.",
            execution,
        )

    def _has_expired(self) -> bool:
        return self._pending is not None and self._clock() >= self._pending.expires_at

    @staticmethod
    def _is_allowed_expression(proposal: ToolProposal | None) -> bool:
        if proposal is None:
            return False
        expected_action = CONTEXTUAL_EXPRESSION_TARGETS.get(proposal.proposal_id)
        return (
            expected_action is not None
            and proposal.permission is PermissionLevel.MUTATING
            and proposal.tool_name == "vector.perform_action"
            and dict(proposal.arguments) == {"action": expected_action}
        )

    @staticmethod
    def _confirmation_result(
        pending: _PendingProposal,
    ) -> ContextualToolTurnResult:
        return ControlledContextualToolConversation._result(
            ContextualToolTurnStatus.AWAITING_CONFIRMATION,
            f"Ich könnte passend dazu '{pending.label}' ausführen. "
            "Soll ich das tun? Antworte mit Ja oder Nein.",
        )

    @staticmethod
    def _blocked_result() -> ContextualToolTurnResult:
        return ControlledContextualToolConversation._result(
            ContextualToolTurnStatus.BLOCKED,
            "Ich kann daraus keinen sicheren Aktionsvorschlag ableiten.",
        )

    @staticmethod
    def _result(
        status: ContextualToolTurnStatus,
        message: str,
        execution: ToolExecutionResult | None = None,
    ) -> ContextualToolTurnResult:
        return ContextualToolTurnResult(status, message, True, execution)


def _extract_proposal_request(user_text: str) -> str | None:
    stripped = user_text.strip()
    normalized = stripped.casefold()
    for prefix in PROPOSAL_REQUEST_PREFIXES:
        if normalized == prefix:
            return ""
        if not normalized.startswith(prefix):
            continue
        remainder = stripped[len(prefix):]
        if remainder and remainder[0] not in PROPOSAL_REQUEST_SEPARATORS:
            continue
        return remainder.lstrip(PROPOSAL_REQUEST_SEPARATORS).strip()
    return None


def _normalize_choice(value: str) -> str:
    return " ".join(value.casefold().strip().rstrip(".!?").split())
