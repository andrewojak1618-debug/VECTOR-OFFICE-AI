"""Persist bounded, content-free runtime diagnostics as local JSON lines."""

import json
import re
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


EVENT_SCHEMA_VERSION = 1
DEFAULT_MAX_BYTES = 1_000_000
EVENT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{1,63}$")
ALLOWED_DETAIL_FIELDS = frozenset({
    "attempt",
    "cloud_allowed",
    "count",
    "duration_ms",
    "error_code",
    "fallback",
    "input_mode",
    "local",
    "max_attempts",
    "provider",
    "reason_code",
    "retry_delay_seconds",
    "status",
    "timeout_seconds",
})
SAFE_VALUE_TYPES = (bool, float, int, str, type(None))


class DiagnosticLevel(Enum):
    """Define the fixed severity vocabulary for runtime diagnostics."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ProviderEvent(Enum):
    """Definiert den festen Lebenszyklus diagnostizierter Provideraufrufe."""

    STARTED = "provider.started"
    FINISHED = "provider.finished"
    TIMEOUT = "provider.timeout"
    ERROR = "provider.error"
    FALLBACK = "provider.fallback"
    RECOVERED = "provider.recovered"


class ProviderErrorCode(Enum):
    """Definiert inhaltsfreie Fehlerklassen ohne interne Fehlermeldungen."""

    REQUEST_TIMEOUT = "request-timeout"
    PROVIDER_UNAVAILABLE = "provider-unavailable"
    INVALID_RESPONSE = "invalid-response"
    PRIMARY_UNAVAILABLE = "primary-unavailable"
    HEALTH_CHECK_FAILED = "health-check-failed"


PROVIDER_EVENT_LEVELS = {
    ProviderEvent.STARTED: DiagnosticLevel.INFO,
    ProviderEvent.FINISHED: DiagnosticLevel.INFO,
    ProviderEvent.TIMEOUT: DiagnosticLevel.WARNING,
    ProviderEvent.ERROR: DiagnosticLevel.ERROR,
    ProviderEvent.FALLBACK: DiagnosticLevel.WARNING,
    ProviderEvent.RECOVERED: DiagnosticLevel.INFO,
}


class ProviderOperation:
    """Erfasst einen Provideraufruf ausschließlich über sichere Metadaten."""

    def __init__(
        self,
        diagnostics: "StructuredDiagnosticReporter | None",
        provider: str,
        clock: Callable[[], float] = time.monotonic,
    ):
        """Startet die inhaltsfreie Zeitmessung eines einzelnen Provideraufrufs."""
        self.diagnostics = diagnostics
        self.provider = provider
        self.clock = clock
        self.started_at = clock()
        emit_provider_event(diagnostics, ProviderEvent.STARTED, provider)

    def finished(self) -> None:
        """Meldet den erfolgreichen Abschluss mit begrenzter Laufzeitangabe."""
        self._complete(ProviderEvent.FINISHED)

    def timeout(self) -> None:
        """Meldet eine Zeitüberschreitung über einen festen sicheren Fehlercode."""
        self._complete(ProviderEvent.TIMEOUT, ProviderErrorCode.REQUEST_TIMEOUT)

    def error(self, error_code: ProviderErrorCode) -> None:
        """Meldet einen Providerfehler ausschließlich über eine feste Fehlerklasse."""
        self._complete(ProviderEvent.ERROR, error_code)

    def _complete(
        self,
        event: ProviderEvent,
        error_code: ProviderErrorCode | None = None,
    ) -> None:
        """Beendet die Messung und übergibt nur zulässige Lebenszyklusdaten."""
        duration_ms = max(0, round((self.clock() - self.started_at) * 1_000))
        emit_provider_event(
            self.diagnostics,
            event,
            self.provider,
            duration_ms=duration_ms,
            error_code=error_code,
        )


def emit_provider_event(
    diagnostics: "StructuredDiagnosticReporter | None",
    event: ProviderEvent,
    provider: str,
    *,
    duration_ms: int | None = None,
    error_code: ProviderErrorCode | None = None,
    fallback: str | None = None,
) -> None:
    """Schreibt ausschließlich freigegebene Metadaten eines Providerereignisses."""
    if not isinstance(event, ProviderEvent):
        raise TypeError("Provider event must be a ProviderEvent value.")
    _validate_provider_name(provider)
    if fallback is not None:
        _validate_provider_name(fallback)
    if error_code is not None and not isinstance(error_code, ProviderErrorCode):
        raise TypeError("Provider error code must be a ProviderErrorCode value.")
    if diagnostics is None:
        return
    details = _provider_details(provider, duration_ms, error_code, fallback)
    diagnostics.emit(
        PROVIDER_EVENT_LEVELS[event],
        provider,
        event.value,
        **details,
    )


def _provider_details(provider, duration_ms, error_code, fallback) -> dict:
    """Erzeugt die feste Metadatenmenge eines Providerereignisses."""
    details = {"provider": provider}
    if duration_ms is not None:
        if type(duration_ms) is not int or duration_ms < 0:
            raise ValueError("Provider duration must be a non-negative integer.")
        details["duration_ms"] = duration_ms
    if error_code is not None:
        details["error_code"] = error_code.value
    if fallback is not None:
        details["fallback"] = fallback
    return details


def _validate_provider_name(provider: str) -> None:
    """Begrenzt Providerbezeichner auf das sichere Ereignisformat."""
    if not isinstance(provider, str) or not EVENT_NAME_PATTERN.fullmatch(provider):
        raise ValueError("Diagnostic provider is invalid.")


class StructuredDiagnosticReporter:
    """Append sanitized diagnostic metadata to one bounded local JSONL file."""

    def __init__(
        self,
        path: str | Path,
        enabled: bool = True,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ):
        """Initialisiert eine begrenzte lokale Diagnoseablage mit Schreibsperre."""
        if type(enabled) is not bool:
            raise TypeError("Diagnostics enabled flag must be boolean.")
        if not 1_024 <= max_bytes <= 10_000_000:
            raise ValueError("Diagnostics size limit must be between 1024 and 10000000.")
        self.path = Path(path).expanduser().resolve()
        self.enabled = enabled
        self.max_bytes = max_bytes
        self._lock = threading.Lock()

    def emit(
        self,
        level: DiagnosticLevel,
        component: str,
        code: str,
        **details: bool | float | int | str | None,
    ) -> bool:
        """Schreibt ein validiertes Ereignis ohne private Inhaltsfelder anzunehmen."""
        if not self.enabled:
            return True
        payload = self._payload(level, component, code, details)
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        try:
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self._rotate_if_needed(len(encoded.encode("utf-8")) + 1)
                with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(f"{encoded}\n")
        except OSError:
            return False
        return True

    @staticmethod
    def _payload(level, component, code, details) -> dict:
        """Validiert und erzeugt ein inhaltsfreies strukturiertes Ereignis."""
        if not isinstance(level, DiagnosticLevel):
            raise TypeError("Diagnostic level must be a DiagnosticLevel value.")
        for name, value in (("component", component), ("code", code)):
            if not isinstance(value, str) or not EVENT_NAME_PATTERN.fullmatch(value):
                raise ValueError(f"Diagnostic {name} is invalid.")
        unknown = set(details) - ALLOWED_DETAIL_FIELDS
        if unknown:
            raise ValueError("Diagnostic details contain a forbidden field.")
        if any(not isinstance(value, SAFE_VALUE_TYPES) for value in details.values()):
            raise TypeError("Diagnostic detail values must be scalar metadata.")
        _validate_detail_metadata(details)
        return {
            "schema_version": EVENT_SCHEMA_VERSION,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "level": level.value,
            "component": component,
            "code": code,
            "details": dict(sorted(details.items())),
        }

    def _rotate_if_needed(self, incoming_bytes: int) -> None:
        """Rotiert die Diagnoseablage vor Überschreiten ihrer festen Größenbegrenzung."""
        if not self.path.exists():
            return
        if self.path.stat().st_size + incoming_bytes <= self.max_bytes:
            return
        rotated = self.path.with_suffix(f"{self.path.suffix}.1")
        if rotated.exists():
            rotated.unlink()
        self.path.replace(rotated)


def _validate_detail_metadata(details: dict) -> None:
    """Begrenzt sicherheitsrelevante Detailwerte auf feste technische Formate."""
    for name in ("provider", "fallback"):
        value = details.get(name)
        if value is not None:
            _validate_provider_name(value)
    duration = details.get("duration_ms")
    if duration is not None and (type(duration) is not int or duration < 0):
        raise ValueError("Diagnostic duration must be a non-negative integer.")
    error_code = details.get("error_code")
    allowed_codes = {item.value for item in ProviderErrorCode}
    if error_code is not None and error_code not in allowed_codes:
        raise ValueError("Diagnostic provider error code is invalid.")
