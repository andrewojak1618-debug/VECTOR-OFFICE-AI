"""Report central provider health without cloud usage or robot actions."""

import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from application.connection_supervisor import (
    CORE_PROVIDERS,
    ConnectionSupervisor,
    ProviderHealth,
)
from application.runtime import get_runtime_mode, register_provider_statuses
from brain.ollama_runtime import OllamaRuntime
from config.settings import settings
from vector.client import VectorClient
from vector.sdk_client import VectorSDKClient


PROBE_TIMEOUT_SECONDS = 6.0
MIN_PROBE_TIMEOUT_SECONDS = 0.1
MAX_PROBE_TIMEOUT_SECONDS = 30.0
LOCAL_PROVIDERS = frozenset({"vector-sdk", "wirepod", "ollama"})
DISPLAY_NAMES = {
    "vector-sdk": "Vector SDK",
    "wirepod": "WirePod",
    "ollama": "Ollama",
    "openai": "OpenAI",
    "elevenlabs": "ElevenLabs",
}
ProviderChecker = Callable[[], bool]
OutputWriter = Callable[[str], None]


@dataclass(frozen=True)
class ProviderDiagnosticResult:
    """Expose one provider state with a fixed, content-free German detail."""

    provider: str
    health: ProviderHealth
    detail: str


@dataclass
class _CheckCapture:
    """Capture only boolean success or failure from one bounded checker."""

    checker: ProviderChecker
    available: bool | None = None
    failed: bool = False

    def run(self) -> None:
        """Führt eine Prüfung aus und verwirft sämtliche internen Fehlerdetails."""
        try:
            self.available = bool(self.checker())
        except Exception:
            self.failed = True


def collect_provider_statuses(
    settings_obj=settings,
    checkers: Mapping[str, ProviderChecker] | None = None,
    timeout: float = PROBE_TIMEOUT_SECONDS,
) -> tuple[ProviderDiagnosticResult, ...]:
    """Prüft lokale Dienste und bewertet Cloud-Provider nur anhand der Konfiguration."""
    _validate_timeout(timeout)
    supervisor = ConnectionSupervisor()
    mode = get_runtime_mode(settings_obj)
    register_provider_statuses(settings_obj, mode, supervisor)
    resolved = _default_checkers(settings_obj) if checkers is None else checkers
    return tuple(
        _inspect_provider(provider, supervisor, resolved, settings_obj, timeout)
        for provider in CORE_PROVIDERS
    )


def run_diagnostic(
    settings_obj=settings,
    checkers: Mapping[str, ProviderChecker] | None = None,
    timeout: float = PROBE_TIMEOUT_SECONDS,
    writer: OutputWriter = print,
) -> bool:
    """Gibt eine deutsche Übersicht aus und meldet vollständige Verfügbarkeit."""
    results = collect_provider_statuses(settings_obj, checkers, timeout)
    writer("Provider-Status (nur lesend):")
    for result in results:
        name = DISPLAY_NAMES[result.provider]
        writer(f"- {name}: {result.health.value} - {result.detail}")
    available = all(
        result.health is not ProviderHealth.UNAVAILABLE
        for result in results
    )
    writer(
        "Gesamtstatus: verfügbar oder kontrolliert eingeschränkt."
        if available
        else "Gesamtstatus: mindestens ein benötigter Dienst ist nicht verfügbar."
    )
    return available


def _inspect_provider(
    provider: str,
    supervisor: ConnectionSupervisor,
    checkers: Mapping[str, ProviderChecker],
    settings_obj,
    timeout: float,
) -> ProviderDiagnosticResult:
    """Ermittelt genau einen Zustand ohne Providerinhalte zu übernehmen."""
    registered = supervisor.provider_status(provider)
    if registered is not None and registered.health is ProviderHealth.DISABLED:
        return ProviderDiagnosticResult(provider, ProviderHealth.DISABLED, "deaktiviert")
    if provider in LOCAL_PROVIDERS:
        health, detail = _check_local(provider, checkers, timeout)
    else:
        health, detail = _check_cloud_configuration(provider, settings_obj)
    supervisor.observe_provider(provider, health)
    return ProviderDiagnosticResult(provider, health, detail)


def _check_local(
    provider: str,
    checkers: Mapping[str, ProviderChecker],
    timeout: float,
) -> tuple[ProviderHealth, str]:
    """Führt einen lokalen Lesecheck unter einer festen äußeren Frist aus."""
    checker = checkers.get(provider)
    if checker is None:
        return ProviderHealth.UNAVAILABLE, "Prüfung nicht verfügbar"
    capture = _CheckCapture(checker)
    worker = threading.Thread(target=capture.run, daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        return ProviderHealth.UNAVAILABLE, "Zeitlimit überschritten"
    if capture.failed:
        return ProviderHealth.UNAVAILABLE, "Prüfung sicher fehlgeschlagen"
    if capture.available:
        return ProviderHealth.HEALTHY, "erreichbar"
    return ProviderHealth.UNAVAILABLE, "nicht erreichbar"


def _check_cloud_configuration(provider: str, settings_obj) -> tuple[ProviderHealth, str]:
    """Prüft Cloud-Felder lokal, ohne Anfrage, Sprache oder Schlüsselausgabe."""
    fields = {
        "openai": ("OPENAI_API_KEY", "OPENAI_MODEL"),
        "elevenlabs": (
            "ELEVENLABS_API_KEY",
            "ELEVENLABS_VOICE_ID",
            "ELEVENLABS_MODEL",
        ),
    }[provider]
    configured = all(_has_text_setting(settings_obj, name) for name in fields)
    if configured:
        return ProviderHealth.DEGRADED, "lokal konfiguriert, nicht live geprüft"
    return ProviderHealth.UNAVAILABLE, "lokale Konfiguration unvollständig"


def _has_text_setting(settings_obj, name: str) -> bool:
    """Prüft ausschließlich, ob ein Einstellungsfeld nicht leeren Text enthält."""
    value = getattr(settings_obj, name, "")
    return isinstance(value, str) and bool(value.strip())


def _default_checkers(settings_obj) -> dict[str, ProviderChecker]:
    """Erzeugt ausschließlich passive lokale Verfügbarkeitsprüfungen."""
    return {
        "vector-sdk": VectorSDKClient(settings_obj.VECTOR_SERIAL).is_available,
        "wirepod": VectorClient(
            settings_obj.WIREPOD_HOST,
            getattr(settings_obj, "WIREPOD_REQUEST_TIMEOUT", 5.0),
        ).is_available,
        "ollama": OllamaRuntime(settings_obj.OLLAMA_HOST).is_available,
    }


def _validate_timeout(timeout: float) -> None:
    """Begrenzt die äußere Frist jeder lokalen Providerprüfung."""
    if (
        type(timeout) not in (int, float)
        or not MIN_PROBE_TIMEOUT_SECONDS <= timeout <= MAX_PROBE_TIMEOUT_SECONDS
    ):
        raise ValueError("Provider status timeout is outside the safe range.")


def main() -> int:
    """Startet den argumentlosen Statusbefehl und liefert einen Prozessstatus."""
    return 0 if run_diagnostic() else 1


if __name__ == "__main__":
    raise SystemExit(main())
