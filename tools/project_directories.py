"""Öffnet ausschließlich fest freigegebene lokale Projektordner."""

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tools.permissions import PermissionLevel
from tools.registry import (
    ToolArguments,
    ToolDefinition,
    ToolOutput,
    ToolParameter,
    ToolParameterType,
    ToolRegistry,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ProjectDirectory:
    """Beschreibt eine feste Ordnerfreigabe ohne frei wählbaren Pfad."""

    identifier: str
    display_name: str
    relative_path: Path
    open_phrases: tuple[str, ...]


PROJECT_DIRECTORIES = (
    ProjectDirectory(
        "documentation",
        "Dokumentationsordner",
        Path("docs"),
        (
            "öffne den dokumentationsordner",
            "öffne bitte den dokumentationsordner",
            "bitte öffne den dokumentationsordner",
            "dokumentationsordner öffnen",
            "öffne die dokumentation",
            "dokumentation öffnen",
        ),
    ),
)

ProjectDirectoryOpener = Callable[[Path], None]


@dataclass(frozen=True)
class ProjectDirectoryOpenTool:
    """Öffnet genau einen erneut geprüften Ordner aus der festen Allowlist."""

    project_root: Path = PROJECT_ROOT
    opener: ProjectDirectoryOpener | None = None

    def __post_init__(self) -> None:
        """Setzt den lokalen Windows-Öffner, wenn keiner injiziert wurde."""
        if self.opener is None:
            object.__setattr__(self, "opener", _open_local_directory)

    @property
    def definition(self) -> ToolDefinition:
        """Beschreibt die bestätigungspflichtige feste Ordneraktion."""
        return ToolDefinition(
            name="development.open_project_directory",
            description="Open one fixed approved project directory by exact identifier.",
            permission=PermissionLevel.MUTATING,
            parameters=(ToolParameter(
                "directory_id",
                "Exact identifier from the fixed project directory allowlist.",
                ToolParameterType.STRING,
            ),),
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Prüft ID und Ziel erneut und öffnet nur den freigegebenen Ordner."""
        directory = _directory_by_identifier(str(arguments["directory_id"]))
        path = _available_directory_path(self.project_root, directory)
        self.opener(path)
        return {
            "directory_id": directory.identifier,
            "display_name": directory.display_name,
            "opened": True,
            "spoken_text": f"Der {directory.display_name} wurde geöffnet.",
        }


def register_project_directory_open_tool(
    registry: ToolRegistry,
    project_root: Path = PROJECT_ROOT,
    opener: ProjectDirectoryOpener | None = None,
) -> None:
    """Registriert das feste bestätigungspflichtige Ordnerwerkzeug."""
    registry.register(ProjectDirectoryOpenTool(project_root, opener))


def _directory_by_identifier(identifier: str) -> ProjectDirectory:
    """Löst ausschließlich eine exakt freigegebene Ordner-ID auf."""
    for directory in PROJECT_DIRECTORIES:
        if identifier == directory.identifier:
            return directory
    raise ValueError("Project directory identifier is not allowlisted.")


def _available_directory_path(root: Path, directory: ProjectDirectory) -> Path:
    """Validiert Ort und Typ des freigegebenen Ordners unmittelbar vor Nutzung."""
    resolved_root = root.resolve()
    path = (resolved_root / directory.relative_path).resolve()
    path.relative_to(resolved_root)
    if not path.exists() or not path.is_dir():
        raise OSError("Approved project directory is unavailable.")
    return path


def _open_local_directory(path: Path) -> None:
    """Öffnet einen bereits geprüften Ordner mit der Windows-Standardaktion."""
    os.startfile(path)
