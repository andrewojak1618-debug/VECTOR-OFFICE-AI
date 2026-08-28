"""Zeigt die letzten sicheren Antwort- und TTS-Zeitwerte aus der Diagnose an."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from config.settings import settings


MAX_REPORT_BYTES = 1_000_000
LATENCY_COMPONENT = "response-latency"
LATENCY_CODES = (
    "response.prepared",
    "response.tts.started",
    "response.tts.finished",
    "response.finished",
)
DISPLAY_LABELS = {
    "response.prepared": "Antwort vorbereitet",
    "response.tts.started": "Zeit bis Wiedergabestart",
    "response.tts.finished": "TTS-Wiedergabe",
    "response.finished": "Gesamter Antwortturn",
}
OutputWriter = Callable[[str], None]


@dataclass(frozen=True)
class LatencyValue:
    """Hält einen validierten Zeitwert und festen technischen Ergebnisstatus."""

    duration_ms: int
    status: str


def collect_latest_latency(path: str | Path) -> dict[str, LatencyValue]:
    """Liest je festem Messpunkt höchstens den letzten sicheren Wert."""
    source = Path(path).expanduser().resolve()
    if not source.is_file() or source.stat().st_size > MAX_REPORT_BYTES:
        return {}
    latest = {}
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    for line in lines:
        _accept_latency_line(line, latest)
    return latest


def run_report(
    path: str | Path | None = None,
    writer: OutputWriter = print,
) -> bool:
    """Gibt ausschließlich feste deutsche Bezeichnungen und Millisekunden aus."""
    source = path if path is not None else settings.DIAGNOSTICS_PATH
    latest = collect_latest_latency(source)
    writer("Antwortlatenz (inhaltsfrei):")
    if not latest:
        writer("- Noch keine vollständigen Messwerte vorhanden.")
        return False
    for code in LATENCY_CODES:
        value = latest.get(code)
        if value is not None:
            writer(
                f"- {DISPLAY_LABELS[code]}: {value.duration_ms} ms "
                f"({value.status})"
            )
    return "response.finished" in latest


def _accept_latency_line(line: str, latest: dict[str, LatencyValue]) -> None:
    """Übernimmt aus einer JSON-Zeile nur bekannte inhaltsfreie Messfelder."""
    try:
        payload = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return
    if payload.get("component") != LATENCY_COMPONENT:
        return
    code = payload.get("code")
    details = payload.get("details", {})
    if code not in LATENCY_CODES or not isinstance(details, dict):
        return
    duration = details.get("duration_ms")
    status = details.get("status")
    if type(duration) is not int or duration < 0:
        return
    if status not in {"active", "success", "failed"}:
        return
    latest[code] = LatencyValue(duration, status)


def main() -> int:
    """Startet den argumentlosen lokalen Bericht mit stabilem Prozessstatus."""
    return 0 if run_report() else 1


if __name__ == "__main__":
    raise SystemExit(main())
