"""Recognize bounded canonical intents without selecting tool parameters."""

import re
from collections.abc import Callable


IntentMatcher = Callable[[str], bool]


def normalize_phrase(value: str) -> str:
    """Normalisiert eine gesprochene Phrase, ohne ihre Originalform aufzubewahren."""
    if not isinstance(value, str):
        return ""
    collapsed = " ".join(value.casefold().strip().split())
    return re.sub(r"[.!?]+$", "", collapsed).strip()


def canonical_phrase(value: str) -> str | None:
    """Liefert nur für eine begrenzt erkannte Absicht eine feste Repräsentativphrase."""
    for matcher, phrase in _CANONICAL_MATCHERS:
        if matcher(value):
            return phrase
    return None


def unmatched_message(value: str) -> str | None:
    """Blockiert erkennbare Faktenabsichten, bevor ein Sprachmodell etwas erfindet."""
    if _looks_like_research_request(value):
        return (
            "Ich habe die Recherchefrage nicht eindeutig erkannt. "
            "Bitte sage: Python Status. Oder: Python Version."
        )
    if _looks_like_project_status_request(value):
        return (
            "Ich habe die Projektstatusfrage nicht eindeutig erkannt. "
            "Bitte frage: Wie ist der Projektstatus?"
        )
    if _looks_like_datetime_request(value):
        return (
            "Ich habe die Datums- oder Uhrzeitfrage nicht eindeutig erkannt. "
            "Bitte frage: Welcher Tag ist heute? Oder: Wie spät ist es?"
        )
    return None


def _looks_like_datetime_request(value: str) -> bool:
    """Erkennt ungenaue Datums- oder Uhrzeitfragen anhand sicherer Schlüsselwörter."""
    words = set(value.split())
    question = bool(words & {"was", "wie", "welcher", "welchen", "welches"})
    date = "heute" in words and bool(words & {"datum", "tag", "wievielte", "wievielten"})
    return question and (date or bool(words & {"uhr", "uhrzeit", "spät"}))


def _looks_like_project_status_request(value: str) -> bool:
    """Erkennt eine erkennbare, aber nicht exakt freigegebene Projektstatusfrage."""
    words = set(value.split())
    request = bool(words & {"wie", "was", "nenne", "zeige", "welcher"})
    return _references_project_status(value) and request


def _looks_like_research_request(value: str) -> bool:
    """Erkennt unklare Python- oder Rechercheanfragen für eine sichere Wiederholung."""
    words = set(value.split())
    research = bool(words & {"python", "recherche", "recherchequelle"})
    target = bool(words & {
        "quelle", "quellen", "prüfen", "überprüfen", "überprüfung", "status", "version",
    })
    return research and target


def _references_project_status(value: str) -> bool:
    """Prüft, ob eine Phrase den festen Projektstatus bezeichnet."""
    words = set(value.split())
    return "projektstatus" in words or {"projekt", "status"} <= words


def _references_latest_project_change(value: str) -> bool:
    """Prüft, ob eine Phrase die letzte dokumentierte Projektänderung meint."""
    words = set(value.split())
    named = "projektänderung" in words or {"projekt", "änderung"} <= words
    described = {"projekt", "zuletzt", "geändert"} <= words
    return named or described


def _references_status(value: str, combined: str, separated: str) -> bool:
    """Erkennt zusammengesetzte oder getrennte Statusbezeichnungen."""
    words = set(value.split())
    return combined in words or {separated, "status"} <= words


def _references_documentation_status(value: str) -> bool:
    """Prüft, ob eine Phrase den festen Dokumentationsstatus bezeichnet."""
    words = set(value.split())
    return "dokumentationsstatus" in words or (
        "status" in words and bool(words & {"dokumentation", "dokumentations"})
    )


def _references_research_source(value: str) -> bool:
    """Prüft, ob eine Phrase die feste Quellen-Erreichbarkeitsprüfung meint."""
    words = set(value.split())
    source = "recherchequelle" in words or {"recherche", "quelle"} <= words
    return (source and bool(words & {"prüfen", "überprüfen"})) or (
        "python" in words and "status" in words
    )


def _references_python_version(value: str) -> bool:
    """Erkennt eine feste Anfrage nach der aktuellen Python-Version."""
    return {"python", "version"} <= set(value.split())


def _references_project_tests(value: str) -> bool:
    """Erkennt eine feste Anfrage nach den lokalen Projekttests."""
    words = set(value.split())
    tests = bool(words & {"test", "tests", "projekttest", "projekttests"})
    return tests and ("projekt" in words or bool(words & {"projekttest", "projekttests"}))


def _references_next_project_item(value: str) -> bool:
    """Erkennt eine Frage nach dem nächsten offenen Projektpunkt."""
    words = set(value.split())
    target = "projektpunkt" in words or "punkt" in words
    sequence = bool(words & {"nächste", "nächster", "nächsten", "nächstes"})
    return target and sequence


_CANONICAL_MATCHERS: tuple[tuple[IntentMatcher, str], ...] = (
    (lambda value: _references_status(value, "gedächtnisstatus", "gedächtnis"), "gedächtnis status"),
    (_references_documentation_status, "dokumentation status"),
    (_references_python_version, "python version"),
    (_references_research_source, "recherchequelle prüfen"),
    (_references_latest_project_change, "projekt änderung"),
    (lambda value: _references_status(value, "bibliotheksstatus", "bibliothek"), "bibliothek status"),
    (lambda value: _references_status(value, "systemstatus", "system"), "system status"),
    (_references_project_tests, "projekt test"),
    (_references_project_status, "wie ist der projektstatus"),
    (_references_next_project_item, "nächster projektpunkt"),
)
