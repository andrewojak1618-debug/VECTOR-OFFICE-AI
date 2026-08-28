"""Recognize bounded canonical intents without selecting tool parameters."""

import re
from collections.abc import Callable


IntentMatcher = Callable[[str], bool]
DOCUMENT_OPEN_ACTIONS = frozenset({"öffne", "öffnen"})
DOCUMENT_OPEN_FILLER = frozenset({"bitte", "die", "den", "das"})
DOCUMENT_OPEN_TARGETS = {
    "dokumentationsordner": "öffne den dokumentationsordner",
    "dokumentations ordner": "öffne den dokumentationsordner",
    "dokumentation": "öffne die dokumentation",
    "dokumentation ordner": "öffne den dokumentationsordner",
    "ordner dokumentation": "öffne den dokumentationsordner",
    "projektübersicht": "öffne die projektübersicht",
    "projekt übersicht": "öffne die projektübersicht",
    "roadmap": "öffne die roadmap",
    "road map": "öffne die roadmap",
    "qualitätsregeln": "öffne die qualitätsregeln",
    "qualitäts regeln": "öffne die qualitätsregeln",
    "werkzeugsicherheit": "öffne die werkzeugsicherheit",
    "werkzeug sicherheit": "öffne die werkzeugsicherheit",
    "windows startanleitung": "öffne die windows startanleitung",
    "windows start anleitung": "öffne die windows startanleitung",
    "firmware sicherheitsregeln": "öffne die firmware sicherheitsregeln",
    "firmware sicherheits regeln": "öffne die firmware sicherheitsregeln",
}
OBSERVED_PROJECT_STATUS_PHRASES = frozenset(
    {"was sagt der projekte einem status aktuell"}
)


def normalize_phrase(value: str) -> str:
    """Normalisiert eine gesprochene Phrase, ohne ihre Originalform aufzubewahren."""
    if not isinstance(value, str):
        return ""
    collapsed = " ".join(value.casefold().strip().split())
    without_punctuation = re.sub(r"[.,!?;:]+", " ", collapsed)
    return " ".join(without_punctuation.split())


def canonical_phrase(value: str) -> str | None:
    """Liefert nur für eine begrenzt erkannte Absicht eine feste Repräsentativphrase."""
    document_open = _canonical_document_open(value)
    if document_open is not None:
        return document_open
    for matcher, phrase in _CANONICAL_MATCHERS:
        if matcher(value):
            return phrase
    return None


def unmatched_message(value: str) -> str | None:
    """Blockiert erkennbare Faktenabsichten, bevor ein Sprachmodell etwas erfindet."""
    if _looks_like_document_open_request(value):
        return (
            "Ich habe die Datei- oder Ordneraktion nicht eindeutig erkannt. "
            "Bitte sage: Bitte öffne die Roadmap. Oder: Bitte öffne den "
            "Dokumentationsordner."
        )
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


def _canonical_document_open(value: str) -> str | None:
    """Normalisiert nur begrenzte Höflichkeits-, Flexions- und Worttrennvarianten."""
    words = value.split()
    actions = tuple(word for word in words if word in DOCUMENT_OPEN_ACTIONS)
    if len(actions) != 1:
        return None
    target_words = tuple(
        word
        for word in words
        if word not in DOCUMENT_OPEN_ACTIONS and word not in DOCUMENT_OPEN_FILLER
    )
    return DOCUMENT_OPEN_TARGETS.get(" ".join(target_words))


def _looks_like_document_open_request(value: str) -> bool:
    """Erkennt nicht eindeutig freigegebene Dateiaktionen für eine sichere Blockierung."""
    words = set(value.split())
    targets = {
        "datei", "dokument", "dokumentation", "dokumentationsordner",
        "firmware", "ordner", "projekt", "projektübersicht",
        "qualität", "qualitätsregeln", "road", "roadmap", "windows",
        "werkzeug", "werkzeugsicherheit",
    }
    return bool(words & DOCUMENT_OPEN_ACTIONS) and bool(words & targets)


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
    if value in OBSERVED_PROJECT_STATUS_PHRASES:
        return True
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


def _references_code_quality_status(value: str) -> bool:
    """Prüft, ob eine Phrase den festen lokalen Codequalitätsstatus bezeichnet."""
    words = set(value.split())
    return "codequalitätsstatus" in words or "codequalität" in words or (
        {"code", "qualität"} <= words
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


def _references_project_plan_summary(value: str) -> bool:
    """Erkennt nur eine Zusammenfassung des fest freigegebenen Projektplans."""
    words = set(value.split())
    target = bool(words & {"roadmap", "projektplan", "projektplanung"}) or (
        {"road", "map"} <= words
    )
    summary = bool(words & {"zusammen", "zusammenfassen", "zusammenfassung"})
    return target and summary


def _bounded_match(
    value: str,
    matcher: IntentMatcher,
    allowed_words: frozenset[str],
) -> bool:
    """Akzeptiert eine kanonische Absicht nur ohne fremde Zusatzanweisungen."""
    return matcher(value) and set(value.split()) <= allowed_words


MEMORY_STATUS_WORDS = frozenset(
    {"wie", "ist", "dein", "gedächtnis", "gedächtnisstatus", "status", "aktuell"}
)
CODE_QUALITY_WORDS = frozenset(
    {
        "wie", "ist", "die", "prüfe", "code", "qualität",
        "codequalität", "codequalitätsstatus", "status",
    }
)
DOCUMENTATION_STATUS_WORDS = frozenset(
    {
        "wie", "ist", "die", "dokumentation", "dokumentations",
        "dokumentationsstatus", "projekt", "status", "vollständig",
    }
)
PYTHON_VERSION_WORDS = frozenset(
    {"python", "version", "aktuelle", "welche", "ist", "was", "die"}
)
RESEARCH_SOURCE_WORDS = frozenset(
    {
        "python", "recherche", "recherchequelle", "quelle", "status",
        "prüfen", "überprüfen", "ist", "die", "erreichbar",
    }
)
LATEST_CHANGE_WORDS = frozenset(
    {
        "projekt", "projektänderung", "änderung", "letzte", "was", "wurde",
        "zuletzt", "am", "geändert", "ist", "die",
    }
)
LIBRARY_STATUS_WORDS = frozenset(
    {"wie", "ist", "der", "bibliothek", "bibliotheksstatus", "status", "aktuell"}
)
SYSTEM_STATUS_WORDS = frozenset(
    {
        "wie", "ist", "der", "system", "systemstatus", "status", "lokaler",
        "sind", "alle", "dienste", "online", "aktuell",
    }
)
PROJECT_TEST_WORDS = frozenset(
    {
        "bitte", "projekt", "test", "tests", "projekttest", "projekttests",
        "starte", "führe", "die", "aus", "ausführen", "teste",
    }
)
PROJECT_STATUS_WORDS = frozenset(
    {
        "wie", "ist", "ihr", "der", "das", "projekt", "projekte", "einem",
        "projektstatus", "status", "was", "sagt", "aktuell", "nenne", "zeige",
    }
)
NEXT_PROJECT_ITEM_WORDS = frozenset(
    {
        "was", "ist", "der", "welcher", "welches", "projektpunkt", "punkt",
        "nächste", "nächster", "nächsten", "nächstes", "wäre", "als", "dran",
        "kommt",
    }
)
PROJECT_PLAN_SUMMARY_WORDS = frozenset(
    {
        "du", "hast", "fasse", "fasste", "die", "den", "der", "im", "in",
        "was", "steht", "road", "map", "roadmap", "projekt", "projektplan",
        "projektplanung", "zusammen", "zusammenfassen", "zusammenfassung",
    }
)


_CANONICAL_MATCHERS: tuple[tuple[IntentMatcher, str], ...] = (
    (
        lambda value: _bounded_match(
            value, _references_project_plan_summary, PROJECT_PLAN_SUMMARY_WORDS
        ),
        "fasse die roadmap zusammen",
    ),
    (
        lambda value: _bounded_match(
            value,
            lambda text: _references_status(text, "gedächtnisstatus", "gedächtnis"),
            MEMORY_STATUS_WORDS,
        ),
        "gedächtnis status",
    ),
    (
        lambda value: _bounded_match(
            value, _references_code_quality_status, CODE_QUALITY_WORDS
        ),
        "codequalität status",
    ),
    (
        lambda value: _bounded_match(
            value, _references_documentation_status, DOCUMENTATION_STATUS_WORDS
        ),
        "dokumentation status",
    ),
    (
        lambda value: _bounded_match(
            value, _references_python_version, PYTHON_VERSION_WORDS
        ),
        "python version",
    ),
    (
        lambda value: _bounded_match(
            value, _references_research_source, RESEARCH_SOURCE_WORDS
        ),
        "recherchequelle prüfen",
    ),
    (
        lambda value: _bounded_match(
            value, _references_latest_project_change, LATEST_CHANGE_WORDS
        ),
        "projekt änderung",
    ),
    (
        lambda value: _bounded_match(
            value,
            lambda text: _references_status(text, "bibliotheksstatus", "bibliothek"),
            LIBRARY_STATUS_WORDS,
        ),
        "bibliothek status",
    ),
    (
        lambda value: _bounded_match(
            value,
            lambda text: _references_status(text, "systemstatus", "system"),
            SYSTEM_STATUS_WORDS,
        ),
        "system status",
    ),
    (
        lambda value: _bounded_match(
            value, _references_project_tests, PROJECT_TEST_WORDS
        ),
        "projekt test",
    ),
    (
        lambda value: _bounded_match(
            value, _references_project_status, PROJECT_STATUS_WORDS
        ),
        "wie ist der projektstatus",
    ),
    (
        lambda value: _bounded_match(
            value, _references_next_project_item, NEXT_PROJECT_ITEM_WORDS
        ),
        "nächster projektpunkt",
    ),
)
