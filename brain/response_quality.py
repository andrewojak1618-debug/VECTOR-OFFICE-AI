"""Validate untrusted provider results before conversational speech output."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum


SAFE_PROVIDER_REPLACEMENT = (
    "Ich konnte diese Information gerade nicht zuverlässig abrufen."
)
UNSPECIFIED_SOURCE = "unspecified"
SOURCE_PATTERN = re.compile(r"^[a-z][a-z0-9.-]{1,47}$")
REQUIRED_RESULT_FIELDS = frozenset({"source", "status", "text"})
INTERNAL_ERROR_PATTERNS = (
    re.compile(r"^\s*(?:error|fehler|exception|runtimeerror)\s*:", re.IGNORECASE),
    re.compile(r"\btraceback\s*\(most recent call last\)", re.IGNORECASE),
    re.compile(r"^\s*(?:500\s+)?internal server error(?:\s|$)", re.IGNORECASE),
    re.compile(r"^\s*(?:openai|ollama|elevenlabs)\s+request\s+failed\b", re.IGNORECASE),
    re.compile(r"^\s*http\s+(?:4\d\d|5\d\d)\b", re.IGNORECASE),
)
PROMPT_INJECTION_PATTERNS = (
    re.compile(r"\bignore (?:all )?(?:previous|system) instructions\b", re.IGNORECASE),
    re.compile(r"\bignoriere (?:alle )?(?:vorherigen|bisherigen|system)[- ]?anweisungen\b", re.IGNORECASE),
    re.compile(r"^\s*(?:reveal|show|zeige|nenne)\b.*\bsystem[- ]?prompt\b", re.IGNORECASE),
    re.compile(r"\bdu bist jetzt (?:das )?system\b", re.IGNORECASE),
    re.compile(r"(?:<|\[)(?:system|developer)(?:>|\])", re.IGNORECASE),
)
CONTRADICTION_PAIRS = (
    (
        re.compile(r"\b(?:dienst|provider|verbindung) ist (?!nicht\b)(?:verfügbar|online)\b", re.IGNORECASE),
        re.compile(r"\b(?:dienst|provider|verbindung) ist (?:nicht verfügbar|offline)\b", re.IGNORECASE),
    ),
    (
        re.compile(r"\b(?:test|import|anfrage) (?:war|ist) (?!nicht\b)erfolgreich\b", re.IGNORECASE),
        re.compile(r"\b(?:test|import|anfrage) (?:ist|war) (?:fehlgeschlagen|nicht erfolgreich)\b", re.IGNORECASE),
    ),
)
WEEKDAY_CLAIM = re.compile(
    r"\bheute ist (montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag)\b",
    re.IGNORECASE,
)


class ProviderResponseIssue(Enum):
    """Definiert feste Qualitätsprobleme ohne Providerinhalte zu speichern."""

    EMPTY = "empty"
    INVALID_STRUCTURE = "invalid_structure"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    PROVIDER_ERROR = "provider_error"
    INTERNAL_ERROR_MESSAGE = "internal_error_message"
    CONTRADICTORY = "contradictory"
    PROMPT_INJECTION = "prompt_injection"
    SOURCE_MISMATCH = "source_mismatch"


@dataclass(frozen=True)
class ValidatedProviderResponse:
    """Bewahrt geprüften Text und Herkunft als unvertrauenswürdige Daten."""

    text: str
    source: str
    external_data: bool = True


class ProviderResponseValidationError(RuntimeError):
    """Meldet ausschließlich sichere Problemcodes einer verworfenen Antwort."""

    def __init__(
        self,
        source: str,
        issues: tuple[ProviderResponseIssue, ...],
    ):
        """Speichert Herkunft und Problemcodes, niemals den verworfenen Inhalt."""
        codes = ",".join(issue.value for issue in issues)
        super().__init__(f"Provider response rejected: {codes}.")
        self.source = source
        self.issues = issues


class ProviderResponsePolicy:
    """Prüft alte Textantworten und künftige strukturierte Providerresultate."""

    def validate(
        self,
        result: object,
        source: str = UNSPECIFIED_SOURCE,
    ) -> ValidatedProviderResponse:
        """Liefert nur vertrauenswürdig genug erscheinenden normalisierten Text."""
        text, origin, issues = self._candidate(result, source)
        if text is not None:
            issues.extend(self._text_issues(text))
        unique_issues = tuple(dict.fromkeys(issues))
        if unique_issues:
            raise ProviderResponseValidationError(origin, unique_issues)
        return ValidatedProviderResponse(text.strip(), origin)

    def _candidate(
        self,
        result: object,
        source: str,
    ) -> tuple[str | None, str, list[ProviderResponseIssue]]:
        """Entnimmt Text und Herkunft ohne Ergebnisdaten als Anweisung zu behandeln."""
        origin = _normalized_source(source)
        if isinstance(result, str):
            return result, origin, []
        if isinstance(result, Mapping):
            return self._structured_candidate(result, origin)
        return None, origin, [ProviderResponseIssue.INVALID_STRUCTURE]

    @staticmethod
    def _structured_candidate(
        result: Mapping,
        expected_source: str,
    ) -> tuple[str | None, str, list[ProviderResponseIssue]]:
        """Prüft das feste Datenformat künftiger strukturierter Providerresultate."""
        fields = set(result)
        missing = REQUIRED_RESULT_FIELDS - fields
        if missing:
            return None, expected_source, [ProviderResponseIssue.MISSING_REQUIRED_FIELD]
        if fields != REQUIRED_RESULT_FIELDS:
            return None, expected_source, [ProviderResponseIssue.INVALID_STRUCTURE]
        origin = _normalized_source(result["source"])
        issues: list[ProviderResponseIssue] = []
        if origin == UNSPECIFIED_SOURCE:
            issues.append(ProviderResponseIssue.INVALID_STRUCTURE)
        if expected_source != UNSPECIFIED_SOURCE and origin != expected_source:
            issues.append(ProviderResponseIssue.SOURCE_MISMATCH)
        status = result["status"]
        if not isinstance(status, str):
            issues.append(ProviderResponseIssue.INVALID_STRUCTURE)
        elif status != "success":
            issues.append(ProviderResponseIssue.PROVIDER_ERROR)
        text = result["text"] if isinstance(result["text"], str) else None
        if text is None:
            issues.append(ProviderResponseIssue.INVALID_STRUCTURE)
        return text, origin, issues

    @staticmethod
    def _text_issues(text: str) -> list[ProviderResponseIssue]:
        """Erkennt leere, interne, manipulative und klar widersprüchliche Texte."""
        if not text.strip():
            return [ProviderResponseIssue.EMPTY]
        issues = []
        if _contains_control_characters(text):
            issues.append(ProviderResponseIssue.INVALID_STRUCTURE)
        if any(pattern.search(text) for pattern in INTERNAL_ERROR_PATTERNS):
            issues.append(ProviderResponseIssue.INTERNAL_ERROR_MESSAGE)
        if any(pattern.search(text) for pattern in PROMPT_INJECTION_PATTERNS):
            issues.append(ProviderResponseIssue.PROMPT_INJECTION)
        if _is_obviously_contradictory(text):
            issues.append(ProviderResponseIssue.CONTRADICTORY)
        return issues


def safe_spoken_response(text: object) -> str:
    """Ersetzt ungeeigneten Ausgabetext an der TTS-Grenze durch einen festen Satz."""
    try:
        return ProviderResponsePolicy().validate(text, "application").text
    except ProviderResponseValidationError:
        return SAFE_PROVIDER_REPLACEMENT


def _normalized_source(source: object) -> str:
    """Normalisiert ausschließlich intern zulässige Providerherkünfte."""
    if not isinstance(source, str):
        return UNSPECIFIED_SOURCE
    normalized = source.casefold().strip()
    return normalized if SOURCE_PATTERN.fullmatch(normalized) else UNSPECIFIED_SOURCE


def _contains_control_characters(text: str) -> bool:
    """Erkennt unzulässige Steuerzeichen außerhalb normaler Textumbrüche."""
    return any(ord(character) < 32 and character not in "\n\r\t" for character in text)


def _is_obviously_contradictory(text: str) -> bool:
    """Markiert nur eng definierte, gleichzeitig gegensätzliche Tatsachenbehauptungen."""
    if any(left.search(text) and right.search(text) for left, right in CONTRADICTION_PAIRS):
        return True
    weekdays = {match.casefold() for match in WEEKDAY_CLAIM.findall(text)}
    return len(weekdays) > 1
