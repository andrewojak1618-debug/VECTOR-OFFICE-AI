"""Sequence confirmed expression animations before German speech output."""

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Protocol

from brain.emotions import ExpressionCue
from brain.expression_actions import ExpressionActionSuggestion
from tools.permissions import PermissionLevel, ToolAuthorization
from tools.registry import ToolExecutionResult, ToolRegistry
from vector.speech import SpeechStyle


EXPRESSION_TOOL_NAME = "vector.perform_action"
EXPRESSION_TARGETS = MappingProxyType(
    {
        ExpressionCue.ATTENTIVE: ("vector.eyes_only", "eyes_only"),
        ExpressionCue.SUPPORTIVE: ("vector.eyes_only", "eyes_only"),
        ExpressionCue.REFLECTIVE: (
            "vector.reflective_expression",
            "reflective_expression",
        ),
    }
)
EXPRESSION_SPEECH_STYLES = MappingProxyType(
    {
        ExpressionCue.NEUTRAL: SpeechStyle.NEUTRAL,
        ExpressionCue.ATTENTIVE: SpeechStyle.NEUTRAL,
        ExpressionCue.SUPPORTIVE: SpeechStyle.NEUTRAL,
        ExpressionCue.REFLECTIVE: SpeechStyle.REFLECTIVE,
    }
)


class SpeechOutput(Protocol):
    """Provide the small speech boundary required by response delivery."""

    def say(
        self,
        text: str,
        style: SpeechStyle = SpeechStyle.NEUTRAL,
    ) -> bool:
        """Speak one response and report whether playback completed."""
        ...


class ExpressionDeliveryStatus(Enum):
    """Classify one privacy-safe response-delivery outcome."""

    SPOKEN_ONLY = "spoken_only"
    ANIMATED_AND_SPOKEN = "animated_and_spoken"
    SPEECH_FAILED = "speech_failed"


@dataclass(frozen=True)
class ExpressionDeliveryResult:
    """Report delivery metadata without retaining the spoken answer."""

    status: ExpressionDeliveryStatus
    action_result: ToolExecutionResult | None = None
    error_code: str | None = None

    @property
    def speech_completed(self) -> bool:
        """Report whether the response finished playing through Vector."""
        return self.status is not ExpressionDeliveryStatus.SPEECH_FAILED


class ExpressionResponseCoordinator:
    """Run one confirmed subtle animation before speech, never in parallel."""

    def __init__(self, registry: ToolRegistry, speech: SpeechOutput):
        if not isinstance(registry, ToolRegistry):
            raise TypeError("Expression delivery requires a ToolRegistry.")
        if not callable(getattr(speech, "say", None)):
            raise TypeError("Expression delivery requires a speech output.")
        self._registry = registry
        self._speech = speech

    def deliver(
        self,
        answer: str,
        suggestion: ExpressionActionSuggestion | None = None,
        authorization: ToolAuthorization | None = None,
        animate: bool = True,
    ) -> ExpressionDeliveryResult:
        """Deliver an answer after an optional, per-call confirmed animation."""
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("Expression response must not be empty.")
        if suggestion is not None and not isinstance(
            suggestion,
            ExpressionActionSuggestion,
        ):
            raise TypeError("Expression suggestion has an invalid type.")
        if type(animate) is not bool:
            raise TypeError("Expression animation flag must be boolean.")
        action_result, action_error = self._run_action(
            suggestion,
            authorization,
            animate,
        )
        if not self._speak(answer, self._speech_style(suggestion)):
            return ExpressionDeliveryResult(
                ExpressionDeliveryStatus.SPEECH_FAILED,
                action_result,
                "speech_playback_failed",
            )
        status = self._spoken_status(action_result)
        return ExpressionDeliveryResult(status, action_result, action_error)

    def _run_action(
        self,
        suggestion: ExpressionActionSuggestion | None,
        authorization: ToolAuthorization | None,
        animate: bool,
    ) -> tuple[ToolExecutionResult | None, str | None]:
        if not animate:
            return None, self._review_error(suggestion)
        if (
            suggestion is None
            or not suggestion.proposed
            or suggestion.review.proposal is None
        ):
            return None, self._review_error(suggestion)
        proposal = suggestion.review.proposal
        if not self._is_fixed_expression(suggestion):
            return None, "expression_proposal_invalid"
        if not self._is_confirmed(authorization):
            return None, "expression_confirmation_required"
        result = self._registry.execute(
            proposal.tool_name,
            proposal.arguments,
            authorization,
        )
        error = None if result.succeeded else result.error_code
        return result, error or (None if result.succeeded else "expression_failed")

    def _speak(self, answer: str, style: SpeechStyle) -> bool:
        try:
            return bool(self._speech.say(answer, style))
        except (RuntimeError, TypeError, ValueError):
            return False

    @staticmethod
    def _speech_style(
        suggestion: ExpressionActionSuggestion | None,
    ) -> SpeechStyle:
        if suggestion is None:
            return SpeechStyle.NEUTRAL
        return EXPRESSION_SPEECH_STYLES.get(
            suggestion.cue,
            SpeechStyle.NEUTRAL,
        )

    @staticmethod
    def _review_error(
        suggestion: ExpressionActionSuggestion | None,
    ) -> str | None:
        if suggestion is None:
            return None
        return suggestion.review.error_code

    @staticmethod
    def _is_confirmed(authorization: ToolAuthorization | None) -> bool:
        return (
            isinstance(authorization, ToolAuthorization)
            and authorization.allow_mutation
            and authorization.confirmed
        )

    @staticmethod
    def _is_fixed_expression(suggestion: ExpressionActionSuggestion) -> bool:
        proposal = suggestion.review.proposal
        target = EXPRESSION_TARGETS.get(suggestion.cue)
        if proposal is None or target is None:
            return False
        proposal_id, action_name = target
        return (
            proposal.proposal_id == proposal_id
            and proposal.tool_name == EXPRESSION_TOOL_NAME
            and proposal.permission is PermissionLevel.MUTATING
            and dict(proposal.arguments) == {"action": action_name}
        )

    @staticmethod
    def _spoken_status(
        action_result: ToolExecutionResult | None,
    ) -> ExpressionDeliveryStatus:
        if action_result is not None and action_result.succeeded:
            return ExpressionDeliveryStatus.ANIMATED_AND_SPOKEN
        return ExpressionDeliveryStatus.SPOKEN_ONLY
