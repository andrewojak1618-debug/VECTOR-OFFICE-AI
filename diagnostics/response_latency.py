"""Misst Antwort- und TTS-Phasen ausschließlich über sichere Zeitmetadaten."""

import time
from collections.abc import Callable

from diagnostics.events import DiagnosticLevel, StructuredDiagnosticReporter


class ResponseLatencyTrace:
    """Erfasst einen sequenziellen Antwortturn ohne Text, Audio oder Kennungen."""

    def __init__(
        self,
        diagnostics: StructuredDiagnosticReporter | None,
        clock: Callable[[], float] = time.monotonic,
    ):
        """Startet eine inhaltsfreie Messung mit einer monotonen lokalen Uhr."""
        if diagnostics is not None and not callable(getattr(diagnostics, "emit", None)):
            raise TypeError("Response latency diagnostics require an emitter.")
        if not callable(clock):
            raise TypeError("Response latency clock must be callable.")
        self.diagnostics = diagnostics
        self.clock = clock
        self.started_at = clock()
        self.speech_started_at: float | None = None
        self.completed = False
        self._emit("response.started", "active")

    def prepared(self) -> None:
        """Meldet die fertige Antwort samt Audio-Vorbereitung seit Turnbeginn."""
        self._emit("response.prepared", "success", self._since(self.started_at))

    def speech_started(self) -> None:
        """Meldet den Wiedergabestart und die bis dahin vergangene Antwortzeit."""
        if self.speech_started_at is not None:
            return
        self.speech_started_at = self.clock()
        self._emit(
            "response.tts.started",
            "active",
            self._duration(self.started_at, self.speech_started_at),
        )

    def speech_finished(self, succeeded: bool) -> None:
        """Meldet ausschließlich Dauer und Ergebnis der TTS-Wiedergabe."""
        if self.speech_started_at is None:
            return
        status = "success" if succeeded else "failed"
        self._emit(
            "response.tts.finished",
            status,
            self._since(self.speech_started_at),
        )

    def finish(self, succeeded: bool) -> None:
        """Beendet den Antwortturn höchstens einmal mit Gesamtdauer und Status."""
        if self.completed:
            return
        self.completed = True
        status = "success" if succeeded else "failed"
        self._emit("response.finished", status, self._since(self.started_at))

    def _since(self, started_at: float) -> int:
        """Berechnet eine nicht negative Millisekundendauer bis zur aktuellen Zeit."""
        return self._duration(started_at, self.clock())

    @staticmethod
    def _duration(started_at: float, finished_at: float) -> int:
        """Rundet eine monotone Zeitspanne sicher auf ganze Millisekunden."""
        return max(0, round((finished_at - started_at) * 1_000))

    def _emit(self, code: str, status: str, duration_ms: int | None = None) -> None:
        """Schreibt nur feste Codes, Status und optionale Millisekunden."""
        if self.diagnostics is None:
            return
        details = {"status": status}
        if duration_ms is not None:
            details["duration_ms"] = duration_ms
        self.diagnostics.emit(
            DiagnosticLevel.INFO,
            "response-latency",
            code,
            **details,
        )
