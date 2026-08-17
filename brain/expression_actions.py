"""Map simulated expression cues to advisory, registry-checked actions."""

from dataclasses import dataclass
from types import MappingProxyType

from brain.emotions import EmotionalState, ExpressionCue
from tools.proposals import (
    ToolProposalReview,
    ToolProposalReviewer,
    ToolProposalStatus,
)


EXPRESSION_PROPOSAL_IDS = MappingProxyType(
    {
        ExpressionCue.NEUTRAL: None,
        ExpressionCue.ATTENTIVE: "vector.eyes_only",
        ExpressionCue.SUPPORTIVE: "vector.eyes_only",
        ExpressionCue.REFLECTIVE: "vector.reflective_expression",
    }
)


@dataclass(frozen=True)
class ExpressionActionSuggestion:
    """Describe one non-executable expression suggestion without user text."""

    cue: ExpressionCue
    state_revision: int
    review: ToolProposalReview

    @property
    def proposed(self) -> bool:
        """Report whether the current registry accepts the mapped proposal."""
        return self.review.status is ToolProposalStatus.PROPOSED


class ExpressionActionMapper:
    """Translate local cue metadata into fixed advisory proposal identifiers."""

    def __init__(self, reviewer: ToolProposalReviewer):
        if not isinstance(reviewer, ToolProposalReviewer):
            raise TypeError("Expression mapper requires a ToolProposalReviewer.")
        self._reviewer = reviewer

    def suggest(self, state: EmotionalState) -> ExpressionActionSuggestion:
        """Return a checked suggestion without authorization or execution."""
        if not isinstance(state, EmotionalState):
            raise TypeError("Expression mapper requires an EmotionalState.")
        proposal_id = self._proposal_id(state)
        review = self._reviewer.resolve(proposal_id)
        return ExpressionActionSuggestion(
            state.expression_cue,
            state.revision,
            review,
        )

    @staticmethod
    def _proposal_id(state: EmotionalState) -> str | None:
        if state.intensity == 0:
            return None
        return EXPRESSION_PROPOSAL_IDS[state.expression_cue]
