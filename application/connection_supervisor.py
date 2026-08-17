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
        if not retry_delays or any(delay < 0 for delay in retry_delays):
            raise ValueError("Connection retry delays must be non-negative.")
        if tuple(sorted(retry_delays)) != retry_delays:
            raise ValueError("Connection retry delays must be ascending.")
        self.diagnostics = diagnostics
        self.retry_delays = retry_delays
        self.sleeper = sleeper
        self._statuses: dict[str, ConnectionStatus] = {}

    def observe(self, service: str, available: bool) -> ConnectionStatus:
        """Record one health result and return the bounded next retry state."""
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
        self._emit(status)
        return status

    def status(self, service: str) -> ConnectionStatus | None:
        """Return the last snapshot for one validated service name."""
        self._validate_service(service)
        return self._statuses.get(service)

    def wait_until_available(
        self,
        service: str,
        health_check: Callable[[], bool],
        max_attempts: int = 5,
    ) -> bool:
        """Run a bounded recovery loop using the configured retry schedule."""
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
        index = min(failure_count - 1, len(self.retry_delays) - 1)
        return self.retry_delays[index]

    @staticmethod
    def _next_failure_count(previous: ConnectionStatus | None) -> int:
        if previous is None or previous.state is ConnectionState.AVAILABLE:
            return 1
        return previous.consecutive_failures + 1

    @staticmethod
    def _validate_service(service: str) -> None:
        if not isinstance(service, str) or not SERVICE_PATTERN.fullmatch(service):
            raise ValueError("Connection service name is invalid.")
