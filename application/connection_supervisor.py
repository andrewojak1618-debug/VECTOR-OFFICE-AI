"""Track local and cloud connectivity with bounded recovery scheduling."""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from diagnostics.events import (
    DiagnosticLevel,
    ProviderErrorCode,
    ProviderEvent,
    ProviderOperation,
    StructuredDiagnosticReporter,
    emit_provider_event,
)


DEFAULT_RETRY_DELAYS = (1.0, 2.0, 5.0, 10.0, 30.0)
SERVICE_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,31}$")
CORE_PROVIDERS = (
    "vector-sdk",
    "wirepod",
    "ollama",
    "openai",
    "elevenlabs",
)


class ConnectionState(Enum):
    """Describe the last observed availability of one service."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class ProviderHealth(Enum):
    """Define the safe public health states of one provider."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


@dataclass(frozen=True)
class ConnectionStatus:
    """Expose one immutable, content-free connection snapshot."""

    service: str
    state: ConnectionState
    consecutive_failures: int
    retry_after_seconds: float
    changed: bool


@dataclass(frozen=True)
class ProviderStatus:
    """Expose one immutable, content-free provider health snapshot."""

    provider: str
    health: ProviderHealth
    changed: bool


class ConnectionSupervisor:
    """Centralize connection state without authorizing robot behavior."""

    def __init__(
        self,
        diagnostics: StructuredDiagnosticReporter | None = None,
        retry_delays: tuple[float, ...] = DEFAULT_RETRY_DELAYS,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        """Initialisiert Zustände, Retryplan, Diagnose und injizierbare Wartefunktion."""
        if not retry_delays or any(delay < 0 for delay in retry_delays):
            raise ValueError("Connection retry delays must be non-negative.")
        if tuple(sorted(retry_delays)) != retry_delays:
            raise ValueError("Connection retry delays must be ascending.")
        self.diagnostics = diagnostics
        self.retry_delays = retry_delays
        self.sleeper = sleeper
        self._statuses: dict[str, ConnectionStatus] = {}
        self._provider_statuses: dict[str, ProviderStatus] = {}
        self._pending_recoveries: set[str] = set()
        self._pending_provider_recoveries: set[str] = set()
        self._provider_recovery_armed: set[str] = set()

    def observe(self, service: str, available: bool) -> ConnectionStatus:
        """Speichert einen Healthcheck und liefert den begrenzten nächsten Retryzustand."""
        self._validate_service(service)
        if type(available) is not bool:
            raise TypeError("Connection availability must be boolean.")
        previous = self._statuses.get(service)
        state = (
            ConnectionState.AVAILABLE
            if available
            else ConnectionState.UNAVAILABLE
        )
        failures = 0 if available else self._next_failure_count(previous)
        retry_after = 0.0 if available else self._retry_delay(failures)
        status = ConnectionStatus(
            service,
            state,
            failures,
            retry_after,
            previous is None or previous.state is not state,
        )
        self._statuses[service] = status
        self._update_recovery(previous, status)
        self._emit(status)
        self._sync_provider_status(service, available)
        return status

    def status(self, service: str) -> ConnectionStatus | None:
        """Liefert den letzten Zustand für einen validierten Dienstnamen."""
        self._validate_service(service)
        return self._statuses.get(service)

    def register_provider(self, provider: str, enabled: bool) -> ProviderStatus:
        """Registriert einen Provider als deaktiviert oder noch nicht erreichbar."""
        if type(enabled) is not bool:
            raise TypeError("Provider enabled flag must be boolean.")
        health = ProviderHealth.UNAVAILABLE if enabled else ProviderHealth.DISABLED
        status = self.observe_provider(provider, health)
        self._provider_recovery_armed.discard(provider)
        return status

    def observe_provider(
        self,
        provider: str,
        health: ProviderHealth,
    ) -> ProviderStatus:
        """Speichert den letzten sicheren Providerzustand und meldet Übergänge."""
        self._validate_service(provider)
        if not isinstance(health, ProviderHealth):
            raise TypeError("Provider health must be a ProviderHealth value.")
        previous = self._provider_statuses.get(provider)
        status = ProviderStatus(
            provider,
            health,
            previous is None or previous.health is not health,
        )
        self._provider_statuses[provider] = status
        self._update_provider_recovery(previous, status)
        self._emit_provider(status)
        return status

    def provider_status(self, provider: str) -> ProviderStatus | None:
        """Liefert den letzten inhaltsfreien Zustand eines Providers."""
        self._validate_service(provider)
        return self._provider_statuses.get(provider)

    def provider_overview(self) -> dict[str, str]:
        """Liefert alle bekannten Providerzustände sortiert als sichere Übersicht."""
        return {
            provider: status.health.value
            for provider, status in sorted(self._provider_statuses.items())
        }

    def consume_provider_recovery(self, provider: str) -> bool:
        """Verbraucht genau einmal die Wiederherstellung eines Providers."""
        self._validate_service(provider)
        if provider not in self._pending_provider_recoveries:
            return False
        self._pending_provider_recoveries.remove(provider)
        return True

    def consume_recovery(self, service: str) -> bool:
        """Verbraucht genau einmal einen Wiederherstellungsübergang ohne Dienstdaten."""
        self._validate_service(service)
        if service not in self._pending_recoveries:
            return False
        self._pending_recoveries.remove(service)
        return True

    def wait_until_available(
        self,
        service: str,
        health_check: Callable[[], bool],
        max_attempts: int = 5,
    ) -> bool:
        """Führt eine begrenzte Wiederherstellungsschleife nach festem Retryplan aus."""
        if not 1 <= max_attempts <= len(self.retry_delays):
            raise ValueError("Connection attempts exceed the bounded retry schedule.")
        for attempt in range(1, max_attempts + 1):
            available = self._run_health_check(service, health_check)
            status = self.observe(service, available)
            if status.state is ConnectionState.AVAILABLE:
                return True
            if attempt < max_attempts:
                self.sleeper(status.retry_after_seconds)
        return False

    def _run_health_check(
        self,
        service: str,
        health_check: Callable[[], bool],
    ) -> bool:
        """Fängt Healthcheckfehler ab und meldet nur sichere Lebenszyklusdaten."""
        operation = ProviderOperation(self.diagnostics, service)
        try:
            available = bool(health_check())
        except TimeoutError:
            operation.timeout()
            return False
        except Exception:
            operation.error(ProviderErrorCode.HEALTH_CHECK_FAILED)
            return False
        if available:
            operation.finished()
        else:
            operation.error(ProviderErrorCode.HEALTH_CHECK_FAILED)
        return available

    def _emit(self, status: ConnectionStatus) -> None:
        """Schreibt nur geänderte Verbindungszustände in die strukturierte Diagnose."""
        if self.diagnostics is None or not status.changed:
            return
        self.diagnostics.emit(
            DiagnosticLevel.INFO
            if status.state is ConnectionState.AVAILABLE
            else DiagnosticLevel.WARNING,
            status.service,
            f"connection.{status.state.value}",
            status=status.state.value,
            count=status.consecutive_failures,
            retry_delay_seconds=status.retry_after_seconds,
        )

    def _emit_provider(self, status: ProviderStatus) -> None:
        """Schreibt nur geänderte Providerzustände ohne Inhalte in die Diagnose."""
        if self.diagnostics is None or not status.changed:
            return
        level = (
            DiagnosticLevel.INFO
            if status.health in {ProviderHealth.HEALTHY, ProviderHealth.DISABLED}
            else DiagnosticLevel.WARNING
        )
        self.diagnostics.emit(
            level,
            status.provider,
            f"provider.health.{status.health.value}",
            provider=status.provider,
            status=status.health.value,
        )

    def _sync_provider_status(self, service: str, available: bool) -> None:
        """Spiegelt bekannte Verbindungsprüfungen in die Providerübersicht."""
        if service not in self._provider_statuses:
            return
        health = ProviderHealth.HEALTHY if available else ProviderHealth.UNAVAILABLE
        self.observe_provider(service, health)

    def _retry_delay(self, failure_count: int) -> float:
        """Liefert die begrenzte Wartezeit für eine fortlaufende Fehleranzahl."""
        index = min(failure_count - 1, len(self.retry_delays) - 1)
        return self.retry_delays[index]

    def _update_recovery(self, previous, current: ConnectionStatus) -> None:
        """Merkt einen Übergang von nicht verfügbar zu verfügbar genau einmal vor."""
        if current.state is ConnectionState.UNAVAILABLE:
            self._pending_recoveries.discard(current.service)
            return
        if previous is not None and previous.state is ConnectionState.UNAVAILABLE:
            self._pending_recoveries.add(current.service)

    def _update_provider_recovery(
        self,
        previous: ProviderStatus | None,
        current: ProviderStatus,
    ) -> None:
        """Merkt die Rückkehr eines eingeschränkten Providers genau einmal vor."""
        recoverable = {ProviderHealth.DEGRADED, ProviderHealth.UNAVAILABLE}
        if current.health in recoverable:
            self._pending_provider_recoveries.discard(current.provider)
            self._provider_recovery_armed.add(current.provider)
            return
        if current.health is not ProviderHealth.HEALTHY:
            self._pending_provider_recoveries.discard(current.provider)
            self._provider_recovery_armed.discard(current.provider)
            return
        armed = current.provider in self._provider_recovery_armed
        if armed and previous is not None and previous.health in recoverable:
            self._pending_provider_recoveries.add(current.provider)
            emit_provider_event(
                self.diagnostics,
                ProviderEvent.RECOVERED,
                current.provider,
            )
        self._provider_recovery_armed.discard(current.provider)

    @staticmethod
    def _next_failure_count(previous: ConnectionStatus | None) -> int:
        """Berechnet den nächsten fortlaufenden Fehlerzähler eines Dienstes."""
        if previous is None or previous.state is ConnectionState.AVAILABLE:
            return 1
        return previous.consecutive_failures + 1

    @staticmethod
    def _validate_service(service: str) -> None:
        """Prüft einen Dienstnamen gegen das begrenzte lokale Format."""
        if not isinstance(service, str) or not SERVICE_PATTERN.fullmatch(service):
            raise ValueError("Connection service name is invalid.")
