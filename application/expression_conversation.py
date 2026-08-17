"""Mediate explicit, per-response expression requests and confirmation."""

from dataclasses import dataclass
from enum import Enum

from application.expression_delivery import (
    ExpressionDeliveryResult,
    ExpressionDeliveryStatus,
    ExpressionResponseCoordinator,
)
from brain.agent import Agent
from brain.context import ConversationCheckpoint
from brain.expression_actions import (
    ExpressionActionMapper,
    ExpressionActionSuggestion,
)
from tools.permissions import ToolAuthorization


EXPRESSION_REQUEST_PREFIXES = (
    "antworte mit ausdruck:",
    "antworte mit ausdruck ",
    "mit ausdruck:",
    "mit ausdruck ",
)
CONFIRMATION_PHRASES = frozenset({"ja", "ja bitte", "bestätigen", "ausführen"})
DECLINE_PHRASES = frozenset({"nein", "ohne animation"})
CANCELLATION_PHRASES = frozenset({"abbrechen", "antwort verwerfen"})
CONFIRMATION_MESSAGE = (
    "Soll ich die Antwort mit einer ruhigen Kopf- und Augenbewegung ausgeben? "
    "Antworte mit Ja oder Nein."
)


class ExpressionTurnStatus(Enum):
    """Describe one controlled expression-conversation turn."""

    NOT_HANDLED = "not_handled"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True)
class ExpressionTurnResult:
    """Return one bounded expression turn without exposing pending state."""

    status: ExpressionTurnStatus
    message: str = ""
    speak: bool = False
    delivery: ExpressionDeliveryResult | None = None

    @property
    def handled(self) -> bool:
        """Report whether the input belongs to expression handling."""
        return self.status is not ExpressionTurnStatus.NOT_HANDLED


@dataclass(frozen=True)
class _PendingExpression:
    answer: str
    suggestion: ExpressionActionSuggestion
    checkpoint: ConversationCheckpoint


class ControlledExpressionConversation:
    """Keep one prepared answer until its expression choice is resolved."""

    def __init__(
        self,
        agent: Agent,
        mapper: ExpressionActionMapper,
        coordinator: ExpressionResponseCoordinator,
    ):
        if not isinstance(agent, Agent):
            raise TypeError("Expression conversation requires an Agent.")
        if not isinstance(mapper, ExpressionActionMapper):
            raise TypeError("Expression conversation requires a mapper.")
        if not isinstance(coordinator, ExpressionResponseCoordinator):
            raise TypeError("Expression conversation requires a coordinator.")
        self._agent = agent
        self._mapper = mapper
        self._coordinator = coordinator
        self._pending: _PendingExpression | None = None

    @property
    def awaiting_confirmation(self) -> bool:
        """Report whether one prepared response awaits a separate decision."""
        return self._pending is not None

    def cancel_pending(self) -> bool:
        """Forget a prepared response without executing or speaking it."""
        pending = self._pending
        self._pending = None
        if pending is None:
            return False
        self._agent.context.restore(pending.checkpoint)
        return True

    def handle(self, user_text: str) -> ExpressionTurnResult:
        """Prepare, confirm, decline, or cancel one expressive response."""
        if not isinstance(user_text, str) or not user_text.strip():
            raise ValueError("Expression conversation input must not be empty.")
        if self._pending is not None:
            return self._handle_confirmation(user_text)
        request = _extract_expression_request(user_text)
        if request is None:
            return ExpressionTurnResult(ExpressionTurnStatus.NOT_HANDLED)
        if not request:
            return ExpressionTurnResult(
                ExpressionTurnStatus.FAILED,
                "Nach 'Mit Ausdruck' fehlt die eigentliche Frage.",
                True,
            )
        return self._prepare(request)

    def _prepare(self, request: str) -> ExpressionTurnResult:
        checkpoint = self._agent.context.checkpoint()
        try:
            answer = self._agent.respond(request)
            suggestion = self._mapper.suggest(self._agent.emotional_state.state)
        except (RuntimeError, ValueError):
            self._agent.context.restore(checkpoint)
            return ExpressionTurnResult(
                ExpressionTurnStatus.FAILED,
                "Die Antwort konnte nicht sicher vorbereitet werden.",
                True,
            )
        if not suggestion.proposed:
            return self._deliver(answer, suggestion, animate=False)
        self._pending = _PendingExpression(answer, suggestion, checkpoint)
        return self._confirmation_result()

    def _handle_confirmation(self, user_text: str) -> ExpressionTurnResult:
        normalized = _normalize_choice(user_text)
        if normalized in CANCELLATION_PHRASES:
            self.cancel_pending()
            return ExpressionTurnResult(
                ExpressionTurnStatus.CANCELLED,
                "Die vorbereitete Antwort wurde verworfen.",
                True,
            )
        if normalized not in CONFIRMATION_PHRASES | DECLINE_PHRASES:
            return self._confirmation_result()
        pending = self._pending
        self._pending = None
        authorization = None
        animate = False
        if normalized in CONFIRMATION_PHRASES:
            authorization = ToolAuthorization(
                allow_mutation=True,
                confirmed=True,
            )
            animate = True
        return self._deliver(
            pending.answer,
            pending.suggestion,
            authorization,
            animate,
        )

    def _deliver(
        self,
        answer: str,
        suggestion: ExpressionActionSuggestion | None = None,
        authorization: ToolAuthorization | None = None,
        animate: bool = True,
    ) -> ExpressionTurnResult:
        delivery = self._coordinator.deliver(
            answer,
            suggestion,
            authorization,
            animate,
        )
        status = ExpressionTurnStatus.DELIVERED
        if delivery.status is ExpressionDeliveryStatus.SPEECH_FAILED:
            status = ExpressionTurnStatus.FAILED
        return ExpressionTurnResult(status, answer, delivery=delivery)

    @staticmethod
    def _confirmation_result() -> ExpressionTurnResult:
        return ExpressionTurnResult(
            ExpressionTurnStatus.AWAITING_CONFIRMATION,
            CONFIRMATION_MESSAGE,
            True,
        )


def _extract_expression_request(user_text: str) -> str | None:
    stripped = user_text.strip()
    normalized = stripped.casefold()
    for prefix in EXPRESSION_REQUEST_PREFIXES:
        if normalized.startswith(prefix):
            return stripped[len(prefix):].strip()
    if normalized in {"antworte mit ausdruck", "mit ausdruck"}:
        return ""
    return None


def _normalize_choice(value: str) -> str:
    return " ".join(value.casefold().strip().rstrip(".!?").split())
