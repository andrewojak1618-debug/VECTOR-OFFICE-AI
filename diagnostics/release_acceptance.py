"""Run reproducible core, live-provider, and physical release checks."""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Callable, Sequence

from config.settings import BASE_DIR, settings


CHECK_TIMEOUT_SECONDS = 900
REGRESSION_TARGET_PATTERN = re.compile(
    r"^tests(?:\.[A-Za-z_][A-Za-z0-9_]*){1,3}$"
)
CORE_MODULES = (
    "application",
    "brain",
    "config",
    "diagnostics",
    "memory",
    "tools",
    "vector",
    "voice",
    "main.py",
    "tests",
)


@dataclass(frozen=True)
class AcceptanceCheck:
    """One named subprocess check in a controlled acceptance category."""

    name: str
    category: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class AcceptanceResult:
    """Secret-free result metadata for one completed acceptance check."""

    name: str
    category: str
    passed: bool
    return_code: int
    duration_seconds: float


CheckExecutor = Callable[[AcceptanceCheck], int]


def build_checks(
    python: str,
    live_ollama: bool = False,
    live_openai: bool = False,
    physical_vector: bool = False,
    physical_confirmed: bool = False,
    regression_test: str | None = None,
) -> tuple[AcceptanceCheck, ...]:
    """Erzeugt Prüfungen ohne Netzwerk oder physische Aktionen stillschweigend freizugeben."""
    if physical_vector and not physical_confirmed:
        raise ValueError("Physical Vector checks require explicit confirmation.")
    checks = []
    if regression_test:
        checks.append(_regression_check(python, regression_test))
    checks.extend(_core_checks(python))
    if live_ollama:
        checks.extend(_ollama_checks(python))
    if live_openai:
        checks.append(_module_check("OpenAI connectivity", "live-openai", python, "openai_smoke"))
    if physical_vector:
        checks.extend(_physical_checks(python))
    return tuple(checks)


def run_checks(
    checks: Sequence[AcceptanceCheck],
    executor: CheckExecutor | None = None,
) -> tuple[AcceptanceResult, ...]:
    """Führt alle Prüfungen aus und hält nur sichere Ergebnismetadaten fest."""
    run = executor or _execute_check
    results = []
    for check in checks:
        print(f"[RUN] {check.category}: {check.name}")
        started = perf_counter()
        return_code = run(check)
        duration = round(perf_counter() - started, 3)
        result = AcceptanceResult(
            check.name,
            check.category,
            return_code == 0,
            return_code,
            duration,
        )
        results.append(result)
        print(f"[{'PASS' if result.passed else 'FAIL'}] {check.name}")
    return tuple(results)


def write_report(
    destination: str | Path,
    results: Sequence[AcceptanceResult],
) -> Path:
    """Schreibt atomar einen JSON-Bericht ohne Befehle oder Prozessausgaben."""
    path = Path(destination).expanduser().resolve()
    if path.suffix.casefold() != ".json":
        raise ValueError("Acceptance report destination must be a JSON file.")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "report_type": "vector-office-ai-release-acceptance",
        "version": settings.VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": all(result.passed for result in results),
        "results": [asdict(result) for result in results],
    }
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def main(argv: Sequence[str] | None = None) -> int:
    """Führt gewählte Abnahmestufen aus und liefert einen Prozessstatuscode."""
    parser = _argument_parser()
    arguments = parser.parse_args(argv)
    try:
        checks = build_checks(
            sys.executable,
            live_ollama=arguments.live_ollama,
            live_openai=arguments.live_openai,
            physical_vector=arguments.physical_vector,
            physical_confirmed=arguments.confirm_physical,
            regression_test=arguments.regression_test,
        )
    except ValueError as exc:
        parser.error(str(exc))
    results = run_checks(checks)
    _print_summary(results)
    if arguments.report:
        print(f"Report: {write_report(arguments.report, results)}")
    return 0 if all(result.passed for result in results) else 1


def _core_checks(python: str) -> tuple[AcceptanceCheck, ...]:
    """Definiert die verpflichtenden lokalen Kernprüfungen der Freigabe."""
    return (
        AcceptanceCheck(
            "Complete unit test suite",
            "core",
            (python, "-m", "unittest", "discover", "-s", "tests"),
        ),
        AcceptanceCheck(
            "Python bytecode compilation",
            "core",
            (python, "-m", "compileall", "-q", *CORE_MODULES),
        ),
        AcceptanceCheck(
            "Strict documentation build",
            "core",
            (python, "-m", "mkdocs", "build", "--strict"),
        ),
        AcceptanceCheck("Git whitespace validation", "core", ("git", "diff", "--check")),
    )


def _regression_check(python: str, target: str) -> AcceptanceCheck:
    """Erzeugt einen sicheren Einzeltest vor der vollständigen Testsuite."""
    if not REGRESSION_TARGET_PATTERN.fullmatch(target):
        raise ValueError(
            "Regression test must be a dotted target below tests."
        )
    return AcceptanceCheck(
        "Focused regression test",
        "regression",
        (python, "-m", "unittest", target, "-v"),
    )


def _ollama_checks(python: str) -> tuple[AcceptanceCheck, ...]:
    """Definiert optionale Liveprüfungen für den lokalen Ollama-Dienst."""
    return (
        _module_check("Local embeddings", "live-ollama", python, "embeddings_ollama"),
        _module_check("Hybrid knowledge search", "live-ollama", python, "hybrid_search_ollama"),
        _module_check("Personality examples", "live-ollama", python, "personality_ollama"),
    )


def _physical_checks(python: str) -> tuple[AcceptanceCheck, ...]:
    """Definiert nur ausdrücklich bestätigte physische Vector-Prüfungen."""
    return (
        _module_check("Knowledge to German speech", "physical-vector", python, "knowledge_vector"),
        AcceptanceCheck(
            "Controlled greeting action",
            "physical-vector",
            (python, "-m", "diagnostics.vector_actions", "greeting"),
        ),
    )


def _module_check(
    name: str,
    category: str,
    python: str,
    module: str,
) -> AcceptanceCheck:
    """Erzeugt eine feste Diagnosemodulprüfung ohne freie Befehlsbestandteile."""
    return AcceptanceCheck(name, category, (python, "-m", f"diagnostics.{module}"))


def _execute_check(check: AcceptanceCheck) -> int:
    """Führt eine feste Prüfung mit Zeitlimit und ohne Ausgabeübernahme aus."""
    try:
        completed = subprocess.run(
            check.command,
            cwd=BASE_DIR,
            check=False,
            timeout=CHECK_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 124
    return completed.returncode


def _argument_parser() -> argparse.ArgumentParser:
    """Definiert explizite Freigaben für Live-, Netzwerk- und physische Prüfungen."""
    parser = argparse.ArgumentParser(
        description="Run Vector Office AI release acceptance layers.",
    )
    parser.add_argument("--live-ollama", action="store_true")
    parser.add_argument("--live-openai", action="store_true")
    parser.add_argument("--physical-vector", action="store_true")
    parser.add_argument("--confirm-physical", action="store_true")
    parser.add_argument(
        "--regression-test",
        metavar="TEST",
        help="Run one dotted unittest target before the complete suite.",
    )
    parser.add_argument("--report", metavar="PATH")
    return parser


def _print_summary(results: Sequence[AcceptanceResult]) -> None:
    """Gibt ausschließlich die Anzahl bestandener Abnahmeprüfungen aus."""
    passed = sum(result.passed for result in results)
    print(f"Acceptance summary: {passed}/{len(results)} checks passed.")


if __name__ == "__main__":
    raise SystemExit(main())
