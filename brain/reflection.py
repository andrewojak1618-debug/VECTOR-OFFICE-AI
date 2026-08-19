"""Prepare concise reflection and reject dishonest response patterns."""

import re
from dataclasses import dataclass
from enum import Enum


class ReflectionMode(Enum):
    """Describe whether a turn benefits from explicit reflection guidance."""

    DIRECT = "direct"
    REFLECTIVE = "reflective"


class ResponseIssue(Enum):
    """Classify response patterns that conflict with the personality rules."""

    CLAIMED_EMOTION = "claimed_emotion"
    FALSE_CERTAINTY = "false_certainty"
    LECTURING = "lecturing"
    SENTENCE_FRAGMENT = "sentence_fragment"
    TOO_LONG = "too_long"


@dataclass(frozen=True)
class ReflectionPlan:
    """Carry provider-independent guidance for one user turn."""

    mode: ReflectionMode
    reason: str
    guidance: str
    max_sentences: int

    @property
    def active(self) -> bool:
        """Report whether explicit philosophical reflection is enabled."""
        return self.mode is ReflectionMode.REFLECTIVE


REFLECTION_TERMS = (
    "bewusstsein",
    "ethik",
    "freiheit",
    "gerechtigkeit",
    "lebenssinn",
    "moral",
    "philosoph",
    "reflektiere",
    "sinn des lebens",
    "was bedeutet glück",
)
DETAIL_TERMS = (
    "ausführlich",
    "detailliert",
    "erkläre genauer",
    "längere antwort",
)
DEFAULT_MAX_SENTENCES = 2
DETAILED_MAX_SENTENCES = 8

DIRECT_GUIDANCE = (
    "Beantworte die konkrete Frage direkt in vollständigen, natürlich "
    "gesprochenen deutschen Sätzen. Vermeide Telegrammstil und alleinstehende "
    "Satzfragmente. Markiere Unsicherheit, wenn die Faktenlage sie verlangt."
)
REFLECTION_GUIDANCE = (
    "Reflektiere kurz wie eigenständiges Nachdenken: Trenne Tatsachen von "
    "Deutung und kennzeichne eine "
    "Perspektive als mögliche Sichtweise. Benenne Unsicherheit. Nutze aktive "
    "Verben, bleibe bei höchstens zwei Sätzen, verwende keine abstrakte "
    "Aufzählung und vermeide Manuskriptton. "
    "Beginne mit einem "
    "greifbaren Kerngedanken statt einer Lexikondefinition; bleibe möglichst "
    "unter 18 Wörtern pro Satz."
)

EMOTION_CLAIMS = re.compile(
    r"\b(?:es\s+tut\s+mir\s+leid|ich\s+(?:fühle|empfinde|liebe|hasse|freue\s+mich|"
    r"bin\s+(?:begeistert|besorgt|erleichtert|traurig|glücklich|wütend|"
    r"verletzt)))\b",
    re.IGNORECASE,
)
FALSE_CERTAINTY = re.compile(
    r"\b(?:ich\s+weiß\s+(?:es\s+)?(?:absolut\s+)?sicher|"
    r"ohne\s+jeden\s+zweifel|das\s+ist\s+(?:definitiv|garantiert))\b",
    re.IGNORECASE,
)
LECTURING = re.compile(
    r"\bdu\s+musst\s+(?:einfach|endlich)\b",
    re.IGNORECASE,
)
SENTENCE_FRAGMENT = re.compile(
    r"(?:^|[.!?]\s+)(?:funktioniert|geht|klingt|läuft|passt)\s+"
    r"(?:gut|schlecht|einwandfrei|reibungslos|richtig|falsch)"
    r"(?=\s*(?:[.!?]|[-–—]|$))",
    re.IGNORECASE,
)


class ReflectionPolicy:
    """Activate philosophical guidance only for explicit matching topics."""

    def __init__(self, enabled: bool = True):
        if type(enabled) is not bool:
            raise TypeError("Reflection enabled flag must be boolean.")
        self.enabled = enabled

    def prepare(self, user_text: str) -> ReflectionPlan:
        """Create a deterministic optional plan without invoking a model."""
        if not isinstance(user_text, str) or not user_text.strip():
            raise ValueError("Reflection input must not be empty.")
        if not self.enabled:
            return ReflectionPlan(
                ReflectionMode.DIRECT,
                "reflection-disabled",
                DIRECT_GUIDANCE,
                self._max_sentences(user_text),
            )
        normalized = user_text.casefold()
        if any(term in normalized for term in REFLECTION_TERMS):
            return ReflectionPlan(
                ReflectionMode.REFLECTIVE,
                "philosophical-topic",
                REFLECTION_GUIDANCE,
                self._max_sentences(user_text),
            )
        return ReflectionPlan(
            ReflectionMode.DIRECT,
            "no-reflection-cue",
            DIRECT_GUIDANCE,
            self._max_sentences(user_text),
        )

    @staticmethod
    def _max_sentences(user_text: str) -> int:
        normalized = user_text.casefold()
        if any(term in normalized for term in DETAIL_TERMS):
            return DETAILED_MAX_SENTENCES
        return DEFAULT_MAX_SENTENCES


class ResponseQualityPolicy:
    """Detect dishonest, lecturing, overly long, or fragmentary responses."""

    def issues(
        self,
        response: str,
        max_sentences: int = DEFAULT_MAX_SENTENCES,
    ) -> tuple[ResponseIssue, ...]:
        """Return deterministic issue codes without logging response content."""
        if not isinstance(response, str) or not response.strip():
            raise ValueError("Response assessment requires non-empty text.")
        checks = (
            (ResponseIssue.CLAIMED_EMOTION, EMOTION_CLAIMS),
            (ResponseIssue.FALSE_CERTAINTY, FALSE_CERTAINTY),
            (ResponseIssue.LECTURING, LECTURING),
            (ResponseIssue.SENTENCE_FRAGMENT, SENTENCE_FRAGMENT),
        )
        issues = [issue for issue, pattern in checks if pattern.search(response)]
        if self._sentence_count(response) > max_sentences:
            issues.append(ResponseIssue.TOO_LONG)
        return tuple(issues)

    @staticmethod
    def correction_guidance(
        issues: tuple[ResponseIssue, ...],
        max_sentences: int = DEFAULT_MAX_SENTENCES,
    ) -> str:
        """Build a provider-neutral retry instruction from issue codes only."""
        if not issues:
            raise ValueError("Correction guidance requires at least one issue.")
        codes = ", ".join(issue.value for issue in issues)
        return (
            "Die vorige interne Antwort wurde wegen folgender Stilregel verworfen: "
            f"{codes}. Formuliere die Antwort neu: empathisch, sachlich, kompakt, "
            "in vollständigen, natürlich gesprochenen deutschen Sätzen mit "
            "erkennbarem Subjekt und finitem Verb, ohne Telegrammstil, ohne echte "
            "Gefühle zu behaupten, ohne falsche Gewissheit und ohne belehrenden "
            f"Ton, mit höchstens {max_sentences} Sätzen. Verwende "
            "nicht die Formel 'Es tut mir leid'; schreibe bei Bedarf stattdessen "
            "'Das klingt belastend'. Erwähne diese Korrektur nicht."
        )

    @staticmethod
    def limit_sentences(response: str, maximum: int) -> str:
        """Keep complete leading sentences up to a positive hard limit."""
        if maximum < 1:
            raise ValueError("Sentence limit must be positive.")
        sentences = tuple(
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", response.strip())
            if sentence.strip()
        )
        return " ".join(sentences[:maximum])

    @staticmethod
    def _sentence_count(response: str) -> int:
        endings = re.findall(r"[.!?]+(?:\s+|$)", response.strip())
        return max(1, len(endings))
