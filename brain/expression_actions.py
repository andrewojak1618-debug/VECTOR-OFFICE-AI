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
        """Meldet, ob die aktuelle Registry den zugeordneten Vorschlag akzeptiert."""
        return self.review.status is ToolProposalStatus.PROPOSED


class ExpressionActionMapper:
    """Translate local cue metadata into fixed advisory proposal identifiers."""

    def __init__(self, reviewer: ToolProposalReviewer):
        """Initialisiert die Zuordnung mit einer verpflichtenden Vorschlagsprüfung."""
        if not isinstance(reviewer, ToolProposalReviewer):
            raise TypeError("Expression mapper requires a ToolProposalReviewer.")
        self._reviewer = reviewer

    def suggest(self, state: EmotionalState) -> ExpressionActionSuggestion:
        """Liefert einen geprüften Vorschlag ohne Freigabe oder Ausführung."""
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
        """Ordnet einem aktiven Zustand eine feste Vorschlagskennung zu."""
        if state.intensity == 0:
            return None
        return EXPRESSION_PROPOSAL_IDS[state.expression_cue]
