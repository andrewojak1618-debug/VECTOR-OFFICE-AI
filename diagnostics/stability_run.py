"""Führt einen begrenzten lokalen Stabilitätslauf ohne Inhaltsdaten aus."""

import argparse
import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from application.connection_supervisor import ProviderHealth
from config.settings import BASE_DIR
from diagnostics.provider_status import (
    LOCAL_PROVIDERS,
    ProviderDiagnosticResult,
    collect_provider_statuses,
)


DEFAULT_SAMPLE_COUNT = 10
DEFAULT_INTERVAL_SECONDS = 30.0
MIN_SAMPLE_COUNT = 1
MAX_SAMPLE_COUNT = 120
MIN_INTERVAL_SECONDS = 1.0
MAX_INTERVAL_SECONDS = 60.0
MAX_RUN_SECONDS = 3_600.0
REPORT_PATH = BASE_DIR / "data" / "acceptance" / "stability.json"
ProviderCollector = Callable[[], Sequence[ProviderDiagnosticResult]]
Sleeper = Callable[[float], None]
Clock = Callable[[], float]
OutputWriter = Callable[[str], None]


@dataclass(frozen=True)
class ProviderStabilityMetric:
    """Hält ausschließlich aggregierte Zustandszahlen eines lokalen Providers."""

    provider: str
    healthy_samples: int
    unavailable_samples: int
    transitions: int
    longest_unavailable_streak: int

    @property
    def stable(self) -> bool:
        """Meldet, ob alle Messungen dieses Providers erfolgreich waren."""
        return self.unavailable_samples == 0


@dataclass(frozen=True)
class StabilityReport:
    """Beschreibt einen abgeschlossenen inhaltsfreien lokalen Stabilitätslauf."""

    sample_count: int
    interval_seconds: float
    duration_ms: int
    providers: tuple[ProviderStabilityMetric, ...]

    @property
    def passed(self) -> bool:
        """Meldet, ob jeder lokale Provider in jeder Messung verfügbar war."""
        return all(metric.stable for metric in self.providers)


@dataclass
class _MetricAccumulator:
    """Sammelt begrenzte Zähler ohne Fehler-, Provider- oder Nutzinhalte."""

    provider: str
    healthy_samples: int = 0
    unavailable_samples: int = 0
    transitions: int = 0
    longest_unavailable_streak: int = 0
    _current_unavailable_streak: int = 0
    _previous_available: bool | None = None

    def add(self, available: bool) -> None:
        """Übernimmt einen booleschen Zustand in die begrenzten Kennzahlen."""
        if self._previous_available is not None and self._previous_available != available:
            self.transitions += 1
        self._previous_available = available
        if available:
            self.healthy_samples += 1
            self._current_unavailable_streak = 0
            return
        self.unavailable_samples += 1
        self._current_unavailable_streak += 1
        self.longest_unavailable_streak = max(
            self.longest_unavailable_streak,
            self._current_unavailable_streak,
        )

    def freeze(self) -> ProviderStabilityMetric:
        """Erzeugt eine unveränderliche öffentliche Kennzahlkopie."""
        return ProviderStabilityMetric(
            self.provider,
            self.healthy_samples,
            self.unavailable_samples,
            self.transitions,
            self.longest_unavailable_streak,
        )


def run_stability_check(
    sample_count: int = DEFAULT_SAMPLE_COUNT,
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
    collector: ProviderCollector | None = None,
    sleeper: Sleeper = time.sleep,
    clock: Clock = time.monotonic,
) -> StabilityReport:
    """Misst lokale Provider wiederholt und liefert nur aggregierte Kennzahlen."""
    _validate_schedule(sample_count, interval_seconds)
    resolved_collector = collector or collect_provider_statuses
    accumulators = {
        provider: _MetricAccumulator(provider)
        for provider in sorted(LOCAL_PROVIDERS)
    }
    started = clock()
    for sample_index in range(sample_count):
        states = _collect_local_states(resolved_collector)
        for provider, accumulator in accumulators.items():
            accumulator.add(states.get(provider, False))
        if sample_index + 1 < sample_count:
            sleeper(interval_seconds)
    duration_ms = max(0, round((clock() - started) * 1000))
    return StabilityReport(
        sample_count,
        interval_seconds,
        duration_ms,
        tuple(item.freeze() for item in accumulators.values()),
    )


def write_report(
    report: StabilityReport,
    path: str | Path = REPORT_PATH,
) -> Path:
    """Speichert ausschließlich geprüfte Aggregatwerte als lokales JSON."""
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "passed": report.passed,
        "sample_count": report.sample_count,
        "interval_seconds": report.interval_seconds,
        "duration_ms": report.duration_ms,
        "providers": {
            metric.provider: {
                "healthy_samples": metric.healthy_samples,
                "unavailable_samples": metric.unavailable_samples,
                "transitions": metric.transitions,
                "longest_unavailable_streak": metric.longest_unavailable_streak,
            }
            for metric in report.providers
        },
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def print_report(report: StabilityReport, writer: OutputWriter = print) -> None:
    """Gibt ausschließlich feste deutsche Bezeichnungen und Zähler aus."""
    writer("Lokaler Stabilitätslauf (inhaltsfrei):")
    writer(
        f"- Messungen: {report.sample_count}, Intervall: "
        f"{report.interval_seconds:g} Sekunden"
    )
    for metric in report.providers:
        writer(
            f"- {metric.provider}: verfügbar {metric.healthy_samples}, "
            f"nicht verfügbar {metric.unavailable_samples}, "
            f"Wechsel {metric.transitions}, längste Ausfallserie "
            f"{metric.longest_unavailable_streak}"
        )
    writer("Gesamtergebnis: bestanden." if report.passed else "Gesamtergebnis: auffällig.")


def _collect_local_states(collector: ProviderCollector) -> dict[str, bool]:
    """Reduziert einen Messaufruf auf feste lokale Providernamen und Wahrheitswerte."""
    try:
        results = collector()
    except Exception:
        return {}
    states = {}
    for result in results:
        provider = getattr(result, "provider", None)
        health = getattr(result, "health", None)
        if provider in LOCAL_PROVIDERS:
            states[provider] = health is ProviderHealth.HEALTHY
    return states


def _validate_schedule(sample_count: int, interval_seconds: float) -> None:
    """Begrenzt Anzahl, Abstand und theoretische Gesamtdauer des Laufs."""
    valid_count = type(sample_count) is int and MIN_SAMPLE_COUNT <= sample_count <= MAX_SAMPLE_COUNT
    valid_interval = (
        type(interval_seconds) in (int, float)
        and MIN_INTERVAL_SECONDS <= interval_seconds <= MAX_INTERVAL_SECONDS
    )
    duration = (sample_count - 1) * interval_seconds if valid_interval else MAX_RUN_SECONDS + 1
    if not valid_count or not valid_interval or duration > MAX_RUN_SECONDS:
        raise ValueError("Stability schedule is outside the safe range.")


def _argument_parser() -> argparse.ArgumentParser:
    """Definiert ausschließlich begrenzte Zeitparameter ohne freie Prüfziele."""
    parser = argparse.ArgumentParser(
        description="Run a content-free local Vector stability check.",
    )
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLE_COUNT)
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=DEFAULT_INTERVAL_SECONDS,
    )
    return parser


def main() -> int:
    """Startet den lokalen Stabilitätslauf und speichert seinen festen Bericht."""
    arguments = _argument_parser().parse_args()
    try:
        report = run_stability_check(arguments.samples, arguments.interval_seconds)
    except (KeyboardInterrupt, ValueError):
        print("Stabilitätslauf kontrolliert beendet.")
        return 2
    print_report(report)
    write_report(report)
    print("Lokaler Bericht unter data/acceptance/stability.json gespeichert.")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
