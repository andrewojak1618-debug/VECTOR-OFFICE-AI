"""Track local and cloud connectivity with bounded recovery scheduling."""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from diagnostics.events import DiagnosticLevel, StructuredDiagnosticReporter


DEFAULT_RETRY_DELAYS = (1.0, 2.0, 5.0, 10.0, 30.0)
SERVICE_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,31}$")


class ConnectionState(Enum):
    """Describe the last observed availability of one service."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ConnectionStatus:
    """Expose one immutable, content-free connection snapshot."""

    service: str
    state: ConnectionState
    consecutive_failures: int
    retry_after_seconds: float
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
        self._pending_recoveries: set[str] = set()

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
        return status

    def status(self, service: str) -> ConnectionStatus | None:
        """Liefert den letzten Zustand für einen validierten Dienstnamen."""
        self._validate_service(service)
        return self._statuses.get(service)

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
            status = self.observe(service, bool(health_check()))
            if status.state is ConnectionState.AVAILABLE:
                return True
            if attempt < max_attempts:
                self.sleeper(status.retry_after_seconds)
        return False

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
