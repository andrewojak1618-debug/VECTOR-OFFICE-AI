"""Run one fixed local project test suite behind explicit tool authority."""

import math
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from tools.permissions import PermissionLevel
from tools.registry import ToolArguments, ToolDefinition, ToolOutput, ToolRegistry


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYTHON_EXECUTABLE = Path(sys.executable).resolve()
CORE_TEST_TIMEOUT_SECONDS = 120.0
MAX_TEST_COUNT = 100_000
TEST_COUNT_PATTERN = re.compile(r"Ran (\d+) tests? in")


@dataclass(frozen=True)
class CoreTestSummary:
    """Hold bounded test metadata without retaining subprocess output."""

    passed: bool
    test_count: int
    duration_seconds: float

    def __post_init__(self) -> None:
        if type(self.passed) is not bool:
            raise TypeError("Core test pass state must be boolean.")
        if type(self.test_count) is not int:
            raise TypeError("Core test count must be an integer.")
        if not 0 <= self.test_count <= MAX_TEST_COUNT:
            raise ValueError("Core test count is outside safe bounds.")
        if not math.isfinite(self.duration_seconds):
            raise ValueError("Core test duration must be finite.")
        if not 0 <= self.duration_seconds <= CORE_TEST_TIMEOUT_SECONDS:
            raise ValueError("Core test duration is outside safe bounds.")


TestRunner = Callable[[Path, Path], CoreTestSummary]


@dataclass(frozen=True)
class CoreProjectTestTool:
    """Execute only the fixed local unittest suite after mutation authority."""

    project_root: Path = PROJECT_ROOT
    python_executable: Path = PYTHON_EXECUTABLE
    runner: TestRunner | None = None

    def __post_init__(self) -> None:
        if self.runner is None:
            object.__setattr__(self, "runner", _run_core_tests)

    @property
    def definition(self) -> ToolDefinition:
        """Describe the argument-free confirmed project test action."""
        return ToolDefinition(
            name="development.run_core_tests",
            description="Run the fixed local Python unit test suite.",
            permission=PermissionLevel.MUTATING,
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Return only bounded result metadata and discard raw test output."""
        summary = self.runner(
            self.project_root.resolve(),
            self.python_executable.resolve(),
        )
        if not isinstance(summary, CoreTestSummary):
            raise TypeError("Core project test runner returned an invalid value.")
        return {
            "passed": summary.passed,
            "test_count": summary.test_count,
            "duration_seconds": round(summary.duration_seconds, 2),
            "spoken_text": _spoken_summary(summary),
        }


def register_core_project_test_tool(
    registry: ToolRegistry,
    project_root: Path = PROJECT_ROOT,
    python_executable: Path = PYTHON_EXECUTABLE,
    runner: TestRunner | None = None,
) -> None:
    """Register one fixed local test action without user parameters."""
    registry.register(CoreProjectTestTool(
        project_root,
        python_executable,
        runner,
    ))


def _run_core_tests(project_root: Path, python_executable: Path) -> CoreTestSummary:
    started = perf_counter()
    completed = subprocess.run(
        (
            str(python_executable),
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
        ),
        cwd=project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=CORE_TEST_TIMEOUT_SECONDS,
        check=False,
    )
    duration = perf_counter() - started
    test_count = _extract_test_count(completed.stdout, completed.stderr)
    return CoreTestSummary(completed.returncode == 0, test_count, duration)


def _extract_test_count(stdout: str, stderr: str) -> int:
    matches = TEST_COUNT_PATTERN.findall(f"{stdout}\n{stderr}")
    if not matches:
        return 0
    return min(int(matches[-1]), MAX_TEST_COUNT)


def _spoken_summary(summary: CoreTestSummary) -> str:
    count = _spoken_test_count(summary.test_count)
    if summary.passed:
        return f"Die Projektprüfung war erfolgreich. {count}"
    return f"Die Projektprüfung wurde beendet, aber Tests sind fehlgeschlagen. {count}"


def _spoken_test_count(count: int) -> str:
    if count == 0:
        return "Die Testanzahl konnte nicht sicher bestimmt werden."
    if count == 1:
        return "Ein Test wurde ausgeführt."
    full_hundreds = count - (count % 100)
    remainder = count % 100
    if full_hundreds and remainder:
        return (
            f"Insgesamt wurden {full_hundreds} Tests und weitere "
            f"{remainder} Tests ausgeführt."
        )
    return f"{count} Tests wurden ausgeführt."
