"""Classify bounded spoken decisions for controlled conversations."""

import re
from enum import Enum


CONFIRMATION_WORDS = frozenset({"bestätigen", "ausführen"})
CANCELLATION_WORDS = frozenset({"abbrechen", "abbruch", "verwerfen"})
CANCELLATION_MARKERS = frozenset({"nicht", "nein"})


class ConfirmationDecision(Enum):
    """Describe one safely classified response to a confirmation question."""

    UNKNOWN = "unknown"
    CONFIRM = "confirm"
    REJECT = "reject"
    CANCEL = "cancel"


def classify_confirmation(value: str) -> ConfirmationDecision:
    """Ordnet eine natürliche Antwort konservativ einer Entscheidung zu."""
    normalized = normalize_confirmation(value)
    words = normalized.split()
    if not words:
        return ConfirmationDecision.UNKNOWN
    if CANCELLATION_WORDS.intersection(words):
        return ConfirmationDecision.CANCEL
    if CANCELLATION_MARKERS.intersection(words):
        return ConfirmationDecision.REJECT
    if words[0] == "ja" or normalized in CONFIRMATION_WORDS:
        return ConfirmationDecision.CONFIRM
    return ConfirmationDecision.UNKNOWN


def normalize_confirmation(value: str) -> str:
    """Vereinheitlicht Satzzeichen, Großschreibung und Zwischenräume."""
    if not isinstance(value, str):
        return ""
    words_only = re.sub(r"[^\wäöüß]+", " ", value.casefold())
    return " ".join(words_only.split())
