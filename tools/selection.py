"""Select registered tools from a fixed set of explicit German intents."""

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType

from tools.permissions import PermissionLevel
from tools.registry import ToolArguments, ToolRegistry, ToolValue
from tools.selection_matching import (
    canonical_phrase,
    normalize_phrase,
    unmatched_message,
)


class ToolSelectionStatus(Enum):
    """Describe whether a controlled intent matched and may be proposed."""

    NO_MATCH = "no_match"
    SELECTED = "selected"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ToolIntentRule:
    """Map exact normalized phrases to one predeclared tool invocation."""

    phrases: tuple[str, ...]
    tool_name: str
    label: str
    arguments: tuple[tuple[str, ToolValue], ...] = ()

    def __post_init__(self) -> None:
        """Validiert feste Phrasen, Toolziel, Bezeichnung und Argumentnamen."""
        if not self.phrases or not all(
            isinstance(phrase, str) and phrase.strip() for phrase in self.phrases
        ):
            raise ValueError("Tool intent phrases must not be empty.")
        if not isinstance(self.tool_name, str) or not isinstance(self.label, str):
            raise TypeError("Tool intent target and label must be strings.")
        if not self.tool_name.strip() or not self.label.strip():
            raise ValueError("Tool intent target and label must not be empty.")
        names = tuple(name for name, _value in self.arguments)
        if len(names) != len(set(names)):
            raise ValueError("Tool intent argument names must be unique.")


@dataclass(frozen=True)
class ToolSelection:
    """Return a safe selection decision without retaining original user text."""

    status: ToolSelectionStatus
    tool_name: str = ""
    label: str = ""
    permission: PermissionLevel | None = None
    arguments: ToolArguments = field(default_factory=lambda: MappingProxyType({}))
    message: str = ""


DEFAULT_INTENT_RULES = (
    ToolIntentRule(
        (
            "projekt änderung",
            "projektänderung",
            "letzte projektänderung",
            "was wurde zuletzt am projekt geändert",
            "was ist die letzte projektänderung",
        ),
        "development.latest_change",
        "letzte dokumentierte Projektänderung nennen",
    ),
    ToolIntentRule(
        (
            "python version",
            "aktuelle python version",
            "welche python version ist aktuell",
            "was ist die aktuelle python version",
        ),
        "research.python_latest_version",
        "aktuelle stabile Python-Version prüfen",
    ),
    ToolIntentRule(
        (
            "recherchequelle prüfen",
            "recherchequelle überprüfen",
            "recherche quelle prüfen",
            "recherche quelle überprüfen",
            "recherche status",
            "python quelle prüfen",
            "python quelle status",
            "python status",
            "ist die recherchequelle erreichbar",
        ),
        "research.python_source_status",
        "fest freigegebene Python-Quelle prüfen",
    ),
    ToolIntentRule(
        (
            "dokumentation status",
            "dokumentations status",
            "dokumentationsstatus",
            "wie ist der dokumentationsstatus",
            "wie ist die dokumentation",
            "ist die dokumentation vollständig",
        ),
        "development.documentation_status",
        "lokalen Dokumentationsstatus nennen",
    ),
    ToolIntentRule(
        (
            "gedächtnis status",
            "gedächtnisstatus",
            "wie ist dein gedächtnis",
            "wie ist dein gedächtnis status",
            "wie viele erinnerungen hast du",
            "memory status",
        ),
        "memory.local_status",
        "lokalen Gedächtnisstatus nennen",
    ),
    ToolIntentRule(
        (
            "bibliothek status",
            "bibliotheksstatus",
            "wie ist der bibliothek status",
            "wie ist der bibliotheksstatus",
            "wie viele dokumente kennst du",
            "wie viele dokumente sind in der bibliothek",
        ),
        "knowledge.library_status",
        "lokalen Bibliotheksstatus nennen",
    ),
    ToolIntentRule(
        (
            "system status",
            "systemstatus",
            "wie ist der system status",
            "wie ist der systemstatus",
            "lokaler system status",
            "sind alle dienste online",
        ),
        "system.local_service_status",
        "lokalen Systemstatus prüfen",
    ),
    ToolIntentRule(
        (
            "nächster projektpunkt",
            "nächster punkt",
            "was ist der nächste projektpunkt",
            "was ist der nächste punkt",
            "welcher projektpunkt kommt als nächstes",
            "welcher punkt kommt als nächstes",
            "wie geht es mit dem projekt weiter",
        ),
        "development.next_roadmap_item",
        "nächsten lokalen Projektpunkt nennen",
    ),
    ToolIntentRule(
        (
            "projekt test",
            "projekt tests",
            "projekttest",
            "projekttests",
            "projekte ist",
            "starte den projekt test",
            "starte die projekt tests",
            "führe die projekt tests aus",
            "teste das projekt",
        ),
        "development.run_core_tests",
        "vollständige lokale Projekttests",
    ),
    ToolIntentRule(
        (
            "wie ist der projektstatus",
            "wie ist der projekt status",
            "nenne den projektstatus",
            "nenne den projekt status",
            "zeige den projektstatus",
            "zeige den projekt status",
            "wie steht das projekt",
            "wie ist das projekt",
        ),
        "development.project_status",
        "lokalen Projektstatus nennen",
    ),
    ToolIntentRule(
        ("wie spät ist es", "wie viel uhr ist es", "welche uhrzeit ist es"),
        "office.local_datetime",
        "aktuelle Uhrzeit nennen",
        (("mode", "time"),),
    ),
    ToolIntentRule(
        (
            "welches datum haben wir",
            "welcher tag ist heute",
            "welchen tag haben wir heute",
            "welches datum ist heute",
        ),
        "office.local_datetime",
        "aktuelles Datum nennen",
        (("mode", "date"),),
    ),
    ToolIntentRule(
        ("welche aktionen kannst du", "welche bewegungen kannst du"),
        "vector.list_actions",
        "sichere Aktionen anzeigen",
    ),
    ToolIntentRule(
        ("schau nach oben", "kopf nach oben"),
        "vector.perform_action",
        "Kopf nach oben",
        (("action", "head_up"),),
    ),
    ToolIntentRule(
        ("schau geradeaus", "kopf gerade"),
        "vector.perform_action",
        "Kopf gerade",
        (("action", "head_level"),),
    ),
    ToolIntentRule(
        (
            "hebe deinen lift",
            "hebe deine lift",
            "lift nach oben",
            "hebe deinen arm",
        ),
        "vector.perform_action",
        "Lift anheben",
        (("action", "lift_up"),),
    ),
    ToolIntentRule(
        ("senke deinen lift", "lift nach unten", "senke deinen arm"),
        "vector.perform_action",
        "Lift absenken",
        (("action", "lift_down"),),
    ),
    ToolIntentRule(
        ("begrüße mich", "bitte begrüße mich", "begrüß mich"),
        "vector.perform_action",
        "Begrüßungsanimation",
        (("action", "greeting"),),
    ),
    ToolIntentRule(
        ("zeige deine augen", "augenanimation"),
        "vector.perform_action",
        "Augenanimation",
        (("action", "eyes_only"),),
    ),
    ToolIntentRule(
        ("notfallstopp", "stopp sofort", "vector stopp sofort"),
        "vector.emergency_stop",
        "Notfallstopp",
    ),
)


class ToolIntentSelector:
    """Match only fixed intents whose target still exists in the registry."""

    def __init__(
        self,
        registry: ToolRegistry,
        rules: tuple[ToolIntentRule, ...] = DEFAULT_INTENT_RULES,
    ):
        """Initialisiert die Auswahl mit Registry und festem Intent-Regelwerk."""
        if not isinstance(registry, ToolRegistry):
            raise TypeError("Tool selector requires a ToolRegistry.")
        self.registry = registry
        self._rules = self._index_rules(rules)

    def select(self, user_text: str) -> ToolSelection:
        """Liefert für eine erkannte Nutzerphrase genau eine registrierte sichere Auswahl."""
        normalized = normalize_phrase(user_text)
        rule = self._resolve_rule(normalized)
        if rule is None:
            return _unmatched_selection(normalized)
        definitions = {item.name: item for item in self.registry.definitions()}
        definition = definitions.get(rule.tool_name)
        if definition is None:
            return _blocked_selection("Selected tool is not registered.")
        if definition.permission is PermissionLevel.DANGEROUS:
            return _blocked_selection("Dangerous conversational tools are blocked.")
        return ToolSelection(
            ToolSelectionStatus.SELECTED,
            definition.name,
            rule.label,
            definition.permission,
            MappingProxyType(dict(rule.arguments)),
        )

    def _resolve_rule(self, normalized: str) -> ToolIntentRule | None:
        """Löst eine exakte oder kanonisch erkannte Phrase auf eine feste Regel auf."""
        rule = self._rules.get(normalized)
        representative = canonical_phrase(normalized) if rule is None else None
        return self._rules.get(representative) if representative else rule

    @staticmethod
    def _index_rules(
        rules: tuple[ToolIntentRule, ...],
    ) -> dict[str, ToolIntentRule]:
        """Indiziert normalisierte eindeutige Intent-Phrasen für konstante Zugriffe."""
        indexed = {}
        for rule in rules:
            if not isinstance(rule, ToolIntentRule):
                raise TypeError("Tool intent rules must be ToolIntentRule values.")
            for phrase in rule.phrases:
                normalized = normalize_phrase(phrase)
                if normalized in indexed:
                    raise ValueError("Tool intent phrases must be unique.")
                indexed[normalized] = rule
        return indexed


def _blocked_selection(message: str) -> ToolSelection:
    """Erzeugt eine blockierte Auswahl mit sicherer Nutzererklärung."""
    return ToolSelection(ToolSelectionStatus.BLOCKED, message=message)


def _unmatched_selection(normalized: str) -> ToolSelection:
    """Blockiert erkennbare Grenzfälle oder meldet eine echte Nichtübereinstimmung."""
    message = unmatched_message(normalized)
    if message is not None:
        return _blocked_selection(message)
    return ToolSelection(ToolSelectionStatus.NO_MATCH)
