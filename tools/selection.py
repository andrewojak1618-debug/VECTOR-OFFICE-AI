"""Select registered tools from a fixed set of explicit German intents."""

import re
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType

from tools.permissions import PermissionLevel
from tools.registry import ToolArguments, ToolRegistry, ToolValue


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
        if not self.phrases or not all(
            isinstance(phrase, str) and phrase.strip()
            for phrase in self.phrases
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
    arguments: ToolArguments = field(
        default_factory=lambda: MappingProxyType({}),
    )
    message: str = ""


DEFAULT_INTENT_RULES = (
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
        if not isinstance(registry, ToolRegistry):
            raise TypeError("Tool selector requires a ToolRegistry.")
        self.registry = registry
        self._rules = self._index_rules(rules)

    def select(self, user_text: str) -> ToolSelection:
        """Return one registered safe selection for an exact user phrase."""
        normalized = _normalize_phrase(user_text)
        rule = self._resolve_rule(normalized)
        if rule is None:
            return _unmatched_selection(normalized)
        definitions = {
            definition.name: definition
            for definition in self.registry.definitions()
        }
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
        rule = self._rules.get(normalized)
        if rule is None and _references_memory_status(normalized):
            rule = self._rules.get("gedächtnis status")
        if rule is None and _references_library_status(normalized):
            rule = self._rules.get("bibliothek status")
        if rule is None and _references_system_status(normalized):
            rule = self._rules.get("system status")
        if rule is None and _references_project_tests(normalized):
            rule = self._rules.get("projekt test")
        if rule is None and _references_project_status(normalized):
            rule = self._rules.get("wie ist der projektstatus")
        return rule

    @staticmethod
    def _index_rules(
        rules: tuple[ToolIntentRule, ...],
    ) -> dict[str, ToolIntentRule]:
        indexed = {}
        for rule in rules:
            if not isinstance(rule, ToolIntentRule):
                raise TypeError("Tool intent rules must be ToolIntentRule values.")
            for phrase in rule.phrases:
                normalized = _normalize_phrase(phrase)
                if normalized in indexed:
                    raise ValueError("Tool intent phrases must be unique.")
                indexed[normalized] = rule
        return indexed


def _normalize_phrase(value: str) -> str:
    if not isinstance(value, str):
        return ""
    collapsed = " ".join(value.casefold().strip().split())
    return re.sub(r"[.!?]+$", "", collapsed).strip()


def _looks_like_datetime_request(value: str) -> bool:
    words = set(value.split())
    question = bool(words & {"was", "wie", "welcher", "welchen", "welches"})
    date = "heute" in words and bool(
        words & {"datum", "tag", "wievielte", "wievielten"}
    )
    clock = bool(words & {"uhr", "uhrzeit", "spät"})
    return question and (date or clock)


def _looks_like_project_status_request(value: str) -> bool:
    words = set(value.split())
    target = _references_project_status(value)
    request = bool(words & {"wie", "was", "nenne", "zeige", "welcher"})
    return target and request


def _references_project_status(value: str) -> bool:
    words = set(value.split())
    return "projektstatus" in words or {"projekt", "status"} <= words


def _references_system_status(value: str) -> bool:
    words = set(value.split())
    return "systemstatus" in words or {"system", "status"} <= words


def _references_library_status(value: str) -> bool:
    words = set(value.split())
    return "bibliotheksstatus" in words or {"bibliothek", "status"} <= words


def _references_memory_status(value: str) -> bool:
    words = set(value.split())
    return "gedächtnisstatus" in words or {"gedächtnis", "status"} <= words


def _references_project_tests(value: str) -> bool:
    words = set(value.split())
    tests = bool(words & {"test", "tests", "projekttest", "projekttests"})
    return tests and ("projekt" in words or bool(words & {"projekttest", "projekttests"}))


def _blocked_selection(message: str) -> ToolSelection:
    return ToolSelection(ToolSelectionStatus.BLOCKED, message=message)


def _unmatched_selection(normalized: str) -> ToolSelection:
    if _looks_like_project_status_request(normalized):
        return _blocked_selection(
            "Ich habe die Projektstatusfrage nicht eindeutig erkannt. "
            "Bitte frage: Wie ist der Projektstatus?",
        )
    if _looks_like_datetime_request(normalized):
        return _blocked_selection(
            "Ich habe die Datums- oder Uhrzeitfrage nicht eindeutig erkannt. "
            "Bitte frage: Welcher Tag ist heute? Oder: Wie spät ist es?",
        )
    return ToolSelection(ToolSelectionStatus.NO_MATCH)
