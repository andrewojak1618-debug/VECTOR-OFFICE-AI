"""Aggregate last-known runtime states into one safe local status overview."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from tools.permissions import PermissionLevel
from tools.registry import ToolArguments, ToolDefinition, ToolOutput, ToolRegistry


StatusOverviewReader = Callable[[], Mapping[str, str]]
LOCAL_PROVIDERS = ("vector-sdk", "wirepod", "ollama")
CLOUD_PROVIDERS = ("openai", "elevenlabs")
SAFE_PROVIDER_STATES = frozenset({
    "healthy",
    "degraded",
    "unavailable",
    "disabled",
})
READY_STATES = frozenset({"healthy", "disabled"})
DISPLAY_NAMES = {
    "vector-sdk": "die Verbindung zu Vector",
    "wirepod": "der lokale Sprachdienst",
    "ollama": "das lokale Sprachmodell",
}


@dataclass(frozen=True)
class LocalStatusOverviewTool:
    """Expose only bounded last-known states without running new provider checks."""

    status_reader: StatusOverviewReader

    @property
    def definition(self) -> ToolDefinition:
        """Beschreibt die argumentlose lokale und rein lesende Übersicht."""
        return ToolDefinition(
            name="system.safe_status_overview",
            description="Return a safe overview of last-known runtime states.",
            permission=PermissionLevel.READ_ONLY,
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Reduziert bekannte Providerzustände auf feste flache Statuswerte."""
        snapshot = _safe_snapshot(self.status_reader)
        local = {
            provider: _local_state(snapshot.get(provider))
            for provider in LOCAL_PROVIDERS
        }
        cloud = {
            provider: _cloud_mode(snapshot.get(provider))
            for provider in CLOUD_PROVIDERS
        }
        overall = _overall_state(local)
        return {
            "application": "healthy",
            "vector_sdk": local["vector-sdk"],
            "wirepod": local["wirepod"],
            "ollama": local["ollama"],
            "openai": cloud["openai"],
            "elevenlabs": cloud["elevenlabs"],
            "cloud_check": "not_performed",
            "overall": overall,
            "spoken_text": _spoken_text(local, overall),
        }


def register_status_overview_tool(
    registry: ToolRegistry,
    status_reader: StatusOverviewReader,
) -> None:
    """Registriert die Übersicht mit dem bestehenden inhaltsfreien Statusleser."""
    registry.register(LocalStatusOverviewTool(status_reader))


def _safe_snapshot(reader: StatusOverviewReader) -> Mapping[str, str]:
    """Fängt Leserfehler ab und übernimmt ausschließlich eine Abbildung."""
    try:
        snapshot = reader()
    except Exception:
        return {}
    return snapshot if isinstance(snapshot, Mapping) else {}


def _local_state(value: object) -> str:
    """Reduziert einen lokalen Providerzustand auf einen erlaubten Wert."""
    return value if isinstance(value, str) and value in SAFE_PROVIDER_STATES else "unknown"


def _cloud_mode(value: object) -> str:
    """Meldet nur lokale Cloud-Konfiguration und behauptet keinen Live-Zustand."""
    if value == "disabled":
        return "disabled"
    if isinstance(value, str) and value in SAFE_PROVIDER_STATES:
        return "configured"
    return "unknown"


def _overall_state(local: Mapping[str, str]) -> str:
    """Fasst lokale Zustände ohne Cloud-Ableitung in drei feste Klassen zusammen."""
    states = tuple(local.values())
    if "unavailable" in states:
        return "attention"
    if all(state in READY_STATES for state in states):
        return "ready"
    return "limited"


def _spoken_text(local: Mapping[str, str], overall: str) -> str:
    """Formuliert höchstens zwei kurze Sätze aus festen lokalen Bezeichnungen."""
    if overall == "ready":
        local_text = _ready_text()
    else:
        local_text = _issue_text(local, overall)
    return f"{local_text} Die Cloud wurde nicht geprüft."


def _ready_text() -> str:
    """Formuliert einen kurzen gemeinsamen Bereitschaftssatz für lokale Dienste."""
    return "Vector ist verbunden und die lokalen Dienste sind bereit."


def _issue_text(local: Mapping[str, str], overall: str) -> str:
    """Nennt nur sichere Dienstbezeichnungen mit eingeschränktem Zustand."""
    affected = [
        DISPLAY_NAMES[provider]
        for provider, state in local.items()
        if state not in READY_STATES
    ]
    names = _join_names(affected)
    condition = _issue_condition(overall, len(affected))
    return f"Vector ist aktiv, aber {names} {condition}."


def _issue_condition(overall: str, affected_count: int) -> str:
    """Wählt eine grammatikalisch passende feste Zustandsbeschreibung."""
    if affected_count == 1:
        return "braucht Aufmerksamkeit" if overall == "attention" else "ist unklar"
    return "brauchen Aufmerksamkeit" if overall == "attention" else "sind unklar"


def _join_names(names: list[str]) -> str:
    """Verbindet höchstens drei feste Dienstnamen zu einer deutschen Aufzählung."""
    if not names:
        return "der lokale Zustand"
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} und {names[-1]}"
