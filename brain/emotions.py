"""Model bounded conversational stances without claiming genuine feelings."""

from dataclasses import dataclass
from enum import Enum


MAX_STANCE_INTENSITY = 2
MAX_TRANSITION_HISTORY = 20


class ConversationStance(Enum):
    """Define the small set of transparent conversational attitudes."""

    NEUTRAL = "neutral"
    SUPPORTIVE = "supportive"
    REFLECTIVE = "reflective"
    CAUTIOUS = "cautious"


class ExpressionCue(Enum):
    """Prepare non-executable cues for a later animation mapping layer."""

    NEUTRAL = "neutral"
    ATTENTIVE = "attentive"
    SUPPORTIVE = "supportive"
    REFLECTIVE = "reflective"


@dataclass(frozen=True)
class EmotionalState:
    """Describe one bounded simulated conversation stance."""

    stance: ConversationStance
    intensity: int
    revision: int
    reason: str
    expression_cue: ExpressionCue

    def __post_init__(self) -> None:
        if not 0 <= self.intensity <= MAX_STANCE_INTENSITY:
            raise ValueError("Emotional-state intensity is outside its bounds.")
        if self.revision < 0:
            raise ValueError("Emotional-state revision must not be negative.")


@dataclass(frozen=True)
class EmotionalTransition:
    """Record one explainable state observation without storing user text."""

    previous: EmotionalState
    current: EmotionalState
    changed: bool


STANCE_TERMS = {
    ConversationStance.SUPPORTIVE: (
        "angst",
        "einsam",
        "schwer",
        "sorge",
        "traurig",
        "überfordert",
        "verzweifelt",
    ),
    ConversationStance.REFLECTIVE: (
        "bewusstsein",
        "ethik",
        "freiheit",
        "gerechtigkeit",
        "lebenssinn",
        "moral",
        "philosoph",
        "sinn des lebens",
        "was bedeutet glück",
    ),
    ConversationStance.CAUTIOUS: (
        "gefährlich",
        "risiko",
        "sicherheit",
        "unsicher",
        "ungewiss",
        "vorsicht",
        "zweifel",
    ),
}

EXPRESSION_CUES = {
    ConversationStance.NEUTRAL: ExpressionCue.NEUTRAL,
    ConversationStance.SUPPORTIVE: ExpressionCue.SUPPORTIVE,
    ConversationStance.REFLECTIVE: ExpressionCue.REFLECTIVE,
    ConversationStance.CAUTIOUS: ExpressionCue.ATTENTIVE,
}

STANCE_GUIDANCE = {
    ConversationStance.NEUTRAL: (
        "Antworte ruhig, natürlich und sachlich."
    ),
    ConversationStance.SUPPORTIVE: (
        "Reagiere behutsam, ohne eigene Gefühle zu behaupten."
    ),
    ConversationStance.REFLECTIVE: (
        "Formuliere nachdenklich und sprechbar: ein klarer Gedanke pro Satz, "
        "mit aktiven Verben und möglichst unter 18 Wörtern. Beginne mit einem "
        "greifbaren Gedanken."
    ),
    ConversationStance.CAUTIOUS: (
        "Benenne Grenzen, Risiken und Unsicherheit ruhig und konkret."
    ),
}


class EmotionalStateModel:
    """Update one session-local stance through bounded deterministic rules."""

    def __init__(self):
        self._state = self._make_state(
            ConversationStance.NEUTRAL,
            intensity=0,
            revision=0,
            reason="initial",
        )
        self._history: list[EmotionalTransition] = []

    @property
    def state(self) -> EmotionalState:
        """Return the current immutable state snapshot."""
        return self._state

    @property
    def history(self) -> tuple[EmotionalTransition, ...]:
        """Return bounded transition metadata without conversation content."""
        return tuple(self._history)

    def observe(self, user_text: str) -> EmotionalTransition:
        """Classify one user turn and apply at most one bounded transition."""
        if not isinstance(user_text, str) or not user_text.strip():
            raise ValueError("Emotional-state input must not be empty.")
        target, reason = self._classify(user_text.casefold())
        previous = self._state
        current = self._transition(previous, target, reason)
        changed = (
            previous.stance is not current.stance
            or previous.intensity != current.intensity
        )
        transition = EmotionalTransition(previous, current, changed)
        self._state = current
        self._history.append(transition)
        self._history = self._history[-MAX_TRANSITION_HISTORY:]
        return transition

    def prompt_guidance(self) -> str:
        """Describe the current simulated stance for any language provider."""
        state = self._state
        return (
            "Simulierte Gesprächshaltung: "
            f"{state.stance.value}, Stufe {state.intensity}. "
            f"{STANCE_GUIDANCE[state.stance]} "
            "Behaupte niemals echte Gefühle oder eigenes Bewusstsein."
        )

    @staticmethod
    def _classify(text: str) -> tuple[ConversationStance, str]:
        for stance, terms in STANCE_TERMS.items():
            if any(term in text for term in terms):
                return stance, f"keyword:{stance.value}"
        return ConversationStance.NEUTRAL, "no-specific-cue"

    @classmethod
    def _transition(
        cls,
        previous: EmotionalState,
        target: ConversationStance,
        reason: str,
    ) -> EmotionalState:
        if target is previous.stance:
            intensity = cls._repeated_intensity(target, previous.intensity)
            stance = target
        elif target is ConversationStance.NEUTRAL:
            intensity = max(0, previous.intensity - 1)
            stance = previous.stance if intensity else target
        else:
            stance, intensity = target, 1
        return cls._make_state(stance, intensity, previous.revision + 1, reason)

    @staticmethod
    def _repeated_intensity(
        stance: ConversationStance,
        previous_intensity: int,
    ) -> int:
        if stance is ConversationStance.NEUTRAL:
            return 0
        return min(MAX_STANCE_INTENSITY, max(1, previous_intensity + 1))

    @staticmethod
    def _make_state(
        stance: ConversationStance,
        intensity: int,
        revision: int,
        reason: str,
    ) -> EmotionalState:
        return EmotionalState(
            stance,
            intensity,
            revision,
            reason,
            EXPRESSION_CUES[stance],
        )
