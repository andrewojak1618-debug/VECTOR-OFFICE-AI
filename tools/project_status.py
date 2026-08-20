"""Expose bounded local project metadata as a read-only development tool."""

import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tools.permissions import PermissionLevel
from tools.registry import ToolArguments, ToolDefinition, ToolOutput, ToolRegistry


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ACCEPTANCE_REPORT = Path("data/acceptance/core.json")
GIT_TIMEOUT_SECONDS = 3.0
MAX_OPEN_CHANGES = 100_000
BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9._/-]{1,80}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{7,40}$")


@dataclass(frozen=True)
class ProjectGitMetadata:
    """Hold validated Git metadata without paths or file contents."""

    branch: str
    commit: str
    open_changes: int

    def __post_init__(self) -> None:
        if BRANCH_PATTERN.fullmatch(self.branch) is None:
            raise ValueError("Project branch contains unsupported characters.")
        if COMMIT_PATTERN.fullmatch(self.commit) is None:
            raise ValueError("Project commit must be a short hexadecimal hash.")
        if type(self.open_changes) is not int:
            raise TypeError("Open project change count must be an integer.")
        if not 0 <= self.open_changes <= MAX_OPEN_CHANGES:
            raise ValueError("Open project change count is outside safe bounds.")


MetadataReader = Callable[[Path], ProjectGitMetadata]
AcceptanceReader = Callable[[Path], bool | None]


@dataclass(frozen=True)
class ProjectStatusTool:
    """Return sanitized status metadata for the fixed local project root."""

    project_root: Path = PROJECT_ROOT
    metadata_reader: MetadataReader | None = None
    acceptance_reader: AcceptanceReader | None = None

    def __post_init__(self) -> None:
        if self.metadata_reader is None:
            object.__setattr__(self, "metadata_reader", _read_git_metadata)
        if self.acceptance_reader is None:
            object.__setattr__(self, "acceptance_reader", _read_acceptance_status)

    @property
    def definition(self) -> ToolDefinition:
        """Describe the argument-free read-only project status tool."""
        return ToolDefinition(
            name="development.project_status",
            description="Return sanitized local project and acceptance metadata.",
            permission=PermissionLevel.READ_ONLY,
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Read fixed metadata without exposing paths, filenames, or content."""
        root = self.project_root.resolve()
        metadata = self.metadata_reader(root)
        if not isinstance(metadata, ProjectGitMetadata):
            raise TypeError("Project metadata reader returned an invalid value.")
        acceptance = self.acceptance_reader(root)
        if acceptance is not None and type(acceptance) is not bool:
            raise TypeError("Acceptance reader returned an invalid value.")
        status = _acceptance_label(acceptance)
        return {
            "branch": metadata.branch,
            "commit": metadata.commit,
            "open_changes": metadata.open_changes,
            "acceptance_status": status,
            "spoken_text": _spoken_status(metadata, acceptance),
        }


def register_project_status_tool(
    registry: ToolRegistry,
    project_root: Path = PROJECT_ROOT,
    metadata_reader: MetadataReader | None = None,
    acceptance_reader: AcceptanceReader | None = None,
) -> None:
    """Register one fixed project status tool without command parameters."""
    registry.register(ProjectStatusTool(
        project_root,
        metadata_reader,
        acceptance_reader,
    ))


def _read_git_metadata(project_root: Path) -> ProjectGitMetadata:
    branch = _git_output(project_root, "branch", "--show-current").strip()
    commit = _git_output(project_root, "log", "-1", "--format=%h").strip()
    status = _git_output(project_root, "status", "--porcelain=v1")
    return ProjectGitMetadata(branch, commit, len(status.splitlines()))


def _git_output(project_root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=GIT_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("Fixed local Git metadata request failed.")
    return completed.stdout


def _read_acceptance_status(project_root: Path) -> bool | None:
    report = (project_root / ACCEPTANCE_REPORT).resolve()
    if not report.is_file():
        return None
    payload = json.loads(report.read_text(encoding="utf-8"))
    if payload.get("report_type") != "vector-office-ai-release-acceptance":
        return None
    passed = payload.get("passed")
    return passed if type(passed) is bool else None


def _spoken_status(metadata: ProjectGitMetadata, acceptance: bool | None) -> str:
    changes = _spoken_changes(metadata.open_changes)
    acceptance_text = {
        True: "Die letzte Kernabnahme war erfolgreich.",
        False: "Die letzte Kernabnahme war nicht erfolgreich.",
        None: "Für die letzte Kernabnahme liegt kein sicherer Status vor.",
    }[acceptance]
    return (
        f"Das Projekt befindet sich auf Branch {metadata.branch}. "
        f"Der letzte Commit ist {metadata.commit}. {changes} {acceptance_text}"
    )


def _spoken_changes(count: int) -> str:
    if count == 0:
        return "Es gibt keine offenen Änderungen."
    if count == 1:
        return "Es gibt eine offene Änderung."
    return f"Es gibt {count} offene Änderungen."


def _acceptance_label(value: bool | None) -> str:
    return {True: "passed", False: "failed", None: "unknown"}[value]
