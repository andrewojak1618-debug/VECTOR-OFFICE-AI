"""Stellt eine inhaltsfreie Übersicht fest freigegebener Projektdokumente bereit."""

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
MAX_DOCUMENT_BYTES = 256_000
VALID_STATES = frozenset({"valid", "missing", "invalid"})


@dataclass(frozen=True)
class ProjectDocument:
    """Beschreibt eine feste Dokumentfreigabe ohne freie Benutzereingaben."""

    identifier: str
    display_name: str
    relative_path: Path
    heading: str
    open_phrases: tuple[str, ...]


PROJECT_DOCUMENTS = (
    ProjectDocument(
        "readme",
        "Projektübersicht",
        Path("README.md"),
        "# 🤖 VECTOR OFFICE AI CORE",
        (
            "öffne die projektübersicht",
            "öffne bitte die projektübersicht",
            "bitte öffne die projektübersicht",
        ),
    ),
    ProjectDocument(
        "roadmap",
        "Roadmap",
        Path("docs/roadmap.md"),
        "# Roadmap",
        (
            "öffne die roadmap",
            "öffne bitte die roadmap",
            "bitte öffne die roadmap",
            "roadmap öffnen",
        ),
    ),
    ProjectDocument(
        "quality",
        "Qualitätsregeln",
        Path("docs/quality.md"),
        "# Codequalität und Projektregeln",
        (
            "öffne die qualitätsregeln",
            "öffne bitte die qualitätsregeln",
            "bitte öffne die qualitätsregeln",
        ),
    ),
    ProjectDocument(
        "tool-security",
        "Werkzeugsicherheit",
        Path("docs/tools-security.md"),
        "# Tool Registry und Berechtigungen",
        (
            "öffne die werkzeugsicherheit",
            "öffne bitte die werkzeugsicherheit",
            "bitte öffne die werkzeugsicherheit",
        ),
    ),
    ProjectDocument(
        "windows-startup",
        "Windows-Startanleitung",
        Path("docs/windows-startup.md"),
        "# Windows-Autostart und Host-Watchdog",
        (
            "öffne die windows startanleitung",
            "öffne bitte die windows startanleitung",
            "bitte öffne die windows startanleitung",
        ),
    ),
    ProjectDocument(
        "firmware-safety",
        "Firmware-Sicherheitsregeln",
        Path("docs/firmware-safety.md"),
        "# Firmware-Sicherheit und kontrollierte Freigabe",
        (
            "öffne die firmware sicherheitsregeln",
            "öffne bitte die firmware sicherheitsregeln",
            "bitte öffne die firmware sicherheitsregeln",
        ),
    ),
)
DOCUMENT_COUNT = len(PROJECT_DOCUMENTS)


@dataclass(frozen=True)
class ProjectDocumentCatalogStatus:
    """Speichert ausschließlich Zustände in der Reihenfolge der festen Freigaben."""

    states: tuple[str, ...]


ProjectDocumentStatusReader = Callable[[Path], ProjectDocumentCatalogStatus]
ProjectDocumentOpener = Callable[[Path], None]


@dataclass(frozen=True)
class ProjectDocumentCatalogTool:
    """Meldet sichere IDs und Anzeigenamen verfügbarer Projektdokumente."""

    project_root: Path = PROJECT_ROOT
    status_reader: ProjectDocumentStatusReader | None = None

    def __post_init__(self) -> None:
        """Setzt den festen Dokumentprüfer, wenn keiner injiziert wurde."""
        if self.status_reader is None:
            object.__setattr__(self, "status_reader", _read_catalog_status)

    @property
    def definition(self) -> ToolDefinition:
        """Beschreibt das argumentlose und rein lesende Katalogwerkzeug."""
        return ToolDefinition(
            name="development.project_document_catalog",
            description="Return safe names for fixed approved project documents.",
            permission=PermissionLevel.READ_ONLY,
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Liefert nur geprüfte Zähler, feste IDs und feste Anzeigenamen."""
        status = self.status_reader(self.project_root.resolve())
        _validate_status(status)
        available = _available_documents(status)
        counts = _state_counts(status)
        return {
            "total_documents": DOCUMENT_COUNT,
            "available_documents": counts["valid"],
            "missing_documents": counts["missing"],
            "invalid_documents": counts["invalid"],
            "document_ids": ", ".join(item.identifier for item in available),
            "display_names": ", ".join(item.display_name for item in available),
            "status": "complete" if counts["valid"] == DOCUMENT_COUNT else "incomplete",
            "spoken_text": _spoken_catalog(available, counts),
        }


def register_project_document_catalog_tool(
    registry: ToolRegistry,
    project_root: Path = PROJECT_ROOT,
    status_reader: ProjectDocumentStatusReader | None = None,
) -> None:
    """Registriert die feste argumentlose Projektdokumentübersicht."""
    registry.register(ProjectDocumentCatalogTool(project_root, status_reader))


@dataclass(frozen=True)
class ProjectDocumentOpenTool:
    """Öffnet genau ein erneut geprüftes Dokument aus der festen Allowlist."""

    project_root: Path = PROJECT_ROOT
    opener: ProjectDocumentOpener | None = None

    def __post_init__(self) -> None:
        """Setzt den lokalen Windows-Öffner, wenn keiner injiziert wurde."""
        if self.opener is None:
            object.__setattr__(self, "opener", _open_local_document)

    @property
    def definition(self) -> ToolDefinition:
        """Beschreibt die bestätigungspflichtige feste Dokumentaktion."""
        return ToolDefinition(
            name="development.open_project_document",
            description="Open one fixed approved project document by exact identifier.",
            permission=PermissionLevel.MUTATING,
            parameters=(ToolParameter(
                "document_id",
                "Exact identifier from the fixed project document allowlist.",
                ToolParameterType.STRING,
            ),),
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Validiert die feste ID und öffnet ausschließlich den geprüften lokalen Pfad."""
        document = _document_by_identifier(str(arguments["document_id"]))
        path = _available_document_path(self.project_root, document)
        self.opener(path)
        return {
            "document_id": document.identifier,
            "display_name": document.display_name,
            "opened": True,
            "spoken_text": f"{document.display_name} wurde geöffnet.",
        }


def register_project_document_open_tool(
    registry: ToolRegistry,
    project_root: Path = PROJECT_ROOT,
    opener: ProjectDocumentOpener | None = None,
) -> None:
    """Registriert das bestätigungspflichtige Öffnen fester Dokumente."""
    registry.register(ProjectDocumentOpenTool(project_root, opener))


def _read_catalog_status(project_root: Path) -> ProjectDocumentCatalogStatus:
    """Prüft ausschließlich die fest im Quellcode freigegebenen Dokumente."""
    states = tuple(
        _document_state(project_root, document)
        for document in PROJECT_DOCUMENTS
    )
    return ProjectDocumentCatalogStatus(states)


def _document_state(root: Path, document: ProjectDocument) -> str:
    """Prüft ein festes Dokument auf Ort, Größe, UTF-8 und Überschrift."""
    resolved_root = root.resolve()
    path = (resolved_root / document.relative_path).resolve()
    try:
        path.relative_to(resolved_root)
        if not path.exists():
            return "missing"
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_DOCUMENT_BYTES:
            return "invalid"
        first_line = path.read_text(encoding="utf-8").splitlines()[:1]
    except (OSError, UnicodeError, ValueError):
        return "invalid"
    return "valid" if first_line == [document.heading] else "invalid"


def _document_by_identifier(identifier: str) -> ProjectDocument:
    """Löst ausschließlich eine exakt freigegebene Dokument-ID auf."""
    for document in PROJECT_DOCUMENTS:
        if identifier == document.identifier:
            return document
    raise ValueError("Project document identifier is not allowlisted.")


def _available_document_path(root: Path, document: ProjectDocument) -> Path:
    """Liefert nur für ein weiterhin gültiges festes Dokument den lokalen Pfad."""
    resolved_root = root.resolve()
    if _document_state(resolved_root, document) != "valid":
        raise OSError("Approved project document is unavailable.")
    path = (resolved_root / document.relative_path).resolve()
    path.relative_to(resolved_root)
    return path


def _open_local_document(path: Path) -> None:
    """Öffnet einen bereits geprüften Pfad über die Windows-Standardanwendung."""
    os.startfile(path)


def _validate_status(status: ProjectDocumentCatalogStatus) -> None:
    """Validiert Anzahl und Werte der inhaltsfreien Dokumentzustände."""
    if not isinstance(status, ProjectDocumentCatalogStatus):
        raise TypeError("Project document reader returned an invalid value.")
    if len(status.states) != DOCUMENT_COUNT:
        raise ValueError("Project document status count does not match the allowlist.")
    if any(type(state) is not str or state not in VALID_STATES for state in status.states):
        raise ValueError("Project document reader returned an invalid state.")


def _available_documents(
    status: ProjectDocumentCatalogStatus,
) -> tuple[ProjectDocument, ...]:
    """Wählt verfügbare Dokumente ausschließlich aus der festen Freigabeliste."""
    return tuple(
        document
        for document, state in zip(PROJECT_DOCUMENTS, status.states, strict=True)
        if state == "valid"
    )


def _state_counts(status: ProjectDocumentCatalogStatus) -> dict[str, int]:
    """Zählt die drei erlaubten Dokumentzustände ohne Pfad- oder Inhaltsdaten."""
    return {state: status.states.count(state) for state in VALID_STATES}


def _spoken_catalog(
    available: tuple[ProjectDocument, ...],
    counts: dict[str, int],
) -> str:
    """Formuliert die feste Dokumentübersicht als begrenzten deutschen Sprechtext."""
    names = ", ".join(document.display_name for document in available)
    if not available:
        return "Aktuell ist kein freigegebenes Projektdokument verfügbar."
    suffix = ""
    if counts["missing"] or counts["invalid"]:
        suffix = " Weitere Freigaben sind derzeit nicht verfügbar."
    return f"Freigegebene Projektdokumente: {names}.{suffix}"
