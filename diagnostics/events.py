"""Persist bounded, content-free runtime diagnostics as local JSON lines."""

import json
import re
import threading
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
