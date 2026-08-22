"""Expose bounded local service availability through one read-only tool."""

from collections.abc import Callable
from dataclasses import dataclass

from tools.permissions import PermissionLevel
from tools.registry import ToolArguments, ToolDefinition, ToolOutput, ToolRegistry


ServiceChecker = Callable[[], bool]


@dataclass(frozen=True)
class LocalServiceStatusTool:
    """Report only whether the fixed local runtime services respond."""

    wirepod_checker: ServiceChecker
    ollama_checker: ServiceChecker

    @property
    def definition(self) -> ToolDefinition:
        """Beschreibt die argumentlose rein lesende lokale Statusabfrage."""
        return ToolDefinition(
            name="system.local_service_status",
            description="Return bounded availability for local runtime services.",
            permission=PermissionLevel.READ_ONLY,
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Prüft feste Dienste, ohne Hosts oder Transportdetails offenzulegen."""
        wirepod = _safe_service_check(self.wirepod_checker)
        ollama = _safe_service_check(self.ollama_checker)
        return {
            "application": True,
            "wirepod": wirepod,
            "ollama": ollama,
            "all_available": wirepod and ollama,
            "spoken_text": _spoken_status(wirepod, ollama),
        }


def register_local_service_status_tool(
    registry: ToolRegistry,
    wirepod_checker: ServiceChecker,
    ollama_checker: ServiceChecker,
) -> None:
    """Registriert feste lokale Healthchecks ohne nutzergesteuerte Ziele."""
    registry.register(LocalServiceStatusTool(wirepod_checker, ollama_checker))


def _safe_service_check(checker: ServiceChecker) -> bool:
    """Führt einen Dienstcheck aus und reduziert Fehler auf nicht verfügbar."""
    try:
        available = checker()
    except Exception:
        return False
    if type(available) is not bool:
        raise TypeError("Local service checker must return a boolean.")
    return available


def _spoken_status(wirepod: bool, ollama: bool) -> str:
    """Fasst die lokalen Dienstzustände in einem deutschen Sprechtext zusammen."""
    wirepod_text = _availability_sentence("WirePod", wirepod)
    ollama_text = _availability_sentence("Ollama", ollama)
    return f"Vector Office AI ist aktiv. {wirepod_text} {ollama_text}"


def _availability_sentence(service: str, available: bool) -> str:
    """Formuliert die lokale Verfügbarkeit eines einzelnen Dienstes."""
    state = "ist lokal verfügbar" if available else "ist lokal nicht erreichbar"
    return f"{service} {state}."
