"""Run reproducible core, live-provider, and physical release checks."""

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Callable, Sequence

from config.settings import BASE_DIR, settings


CHECK_TIMEOUT_SECONDS = 900
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
) -> tuple[AcceptanceCheck, ...]:
    """Build checks without implicitly enabling network or physical actions."""
    if physical_vector and not physical_confirmed:
        raise ValueError("Physical Vector checks require explicit confirmation.")
    checks = list(_core_checks(python))
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
    """Execute every check and retain only safe result metadata."""
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
    """Write an atomic JSON report containing no commands or process output."""
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
    """Run selected acceptance layers and return a process status code."""
    parser = _argument_parser()
    arguments = parser.parse_args(argv)
    try:
        checks = build_checks(
            sys.executable,
            arguments.live_ollama,
            arguments.live_openai,
            arguments.physical_vector,
            arguments.confirm_physical,
        )
    except ValueError as exc:
        parser.error(str(exc))
    results = run_checks(checks)
    _print_summary(results)
    if arguments.report:
        print(f"Report: {write_report(arguments.report, results)}")
    return 0 if all(result.passed for result in results) else 1


def _core_checks(python: str) -> tuple[AcceptanceCheck, ...]:
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


def _ollama_checks(python: str) -> tuple[AcceptanceCheck, ...]:
    return (
        _module_check("Local embeddings", "live-ollama", python, "embeddings_ollama"),
        _module_check("Hybrid knowledge search", "live-ollama", python, "hybrid_search_ollama"),
        _module_check("Personality examples", "live-ollama", python, "personality_ollama"),
    )


def _physical_checks(python: str) -> tuple[AcceptanceCheck, ...]:
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
    return AcceptanceCheck(name, category, (python, "-m", f"diagnostics.{module}"))


def _execute_check(check: AcceptanceCheck) -> int:
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
    parser = argparse.ArgumentParser(
        description="Run Vector Office AI release acceptance layers.",
    )
    parser.add_argument("--live-ollama", action="store_true")
    parser.add_argument("--live-openai", action="store_true")
    parser.add_argument("--physical-vector", action="store_true")
    parser.add_argument("--confirm-physical", action="store_true")
    parser.add_argument("--report", metavar="PATH")
    return parser


def _print_summary(results: Sequence[AcceptanceResult]) -> None:
    passed = sum(result.passed for result in results)
    print(f"Acceptance summary: {passed}/{len(results)} checks passed.")


if __name__ == "__main__":
    raise SystemExit(main())
