"""Expose count-only health for fixed public project documentation."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tools.permissions import PermissionLevel
from tools.registry import ToolArguments, ToolDefinition, ToolOutput, ToolRegistry


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAX_DOCUMENT_BYTES = 256_000
REQUIRED_DOCUMENTS = (
    (Path("README.md"), "# 🤖 VECTOR OFFICE AI CORE"),
    (Path("CHANGELOG.md"), "# Changelog"),
    (Path("docs/architecture.md"), "# Architektur"),
    (Path("docs/roadmap.md"), "# Roadmap"),
    (Path("docs/tools-security.md"), "# Tool Registry und Berechtigungen"),
    (Path("docs/quality.md"), "# Codequalität und Projektregeln"),
)
DOCUMENT_COUNT = len(REQUIRED_DOCUMENTS)


@dataclass(frozen=True)
class DocumentationStatus:
    """Hold content-free counts for the fixed documentation allowlist."""

    valid: int
    missing: int
    invalid: int


DocumentationStatusReader = Callable[[Path], DocumentationStatus]


@dataclass(frozen=True)
class LocalDocumentationStatusTool:
    """Return bounded health counts without paths or document contents."""

    project_root: Path = PROJECT_ROOT
    status_reader: DocumentationStatusReader | None = None

    def __post_init__(self) -> None:
        if self.status_reader is None:
            object.__setattr__(self, "status_reader", _read_documentation_status)

    @property
    def definition(self) -> ToolDefinition:
        """Describe the argument-free local documentation status tool."""
        return ToolDefinition(
            name="development.documentation_status",
            description="Return count-only health for fixed project documents.",
            permission=PermissionLevel.READ_ONLY,
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Return validated counts and a locally generated German summary."""
        status = self.status_reader(self.project_root.resolve())
        _validate_status(status)
        complete = status.valid == DOCUMENT_COUNT
        return {
            "total_documents": DOCUMENT_COUNT,
            "valid_documents": status.valid,
            "missing_documents": status.missing,
            "invalid_documents": status.invalid,
            "status": "complete" if complete else "incomplete",
            "spoken_text": _spoken_status(status),
        }


def register_documentation_status_tool(
    registry: ToolRegistry,
    project_root: Path = PROJECT_ROOT,
    status_reader: DocumentationStatusReader | None = None,
) -> None:
    """Register the fixed argument-free documentation status reader."""
    registry.register(LocalDocumentationStatusTool(project_root, status_reader))


def _read_documentation_status(project_root: Path) -> DocumentationStatus:
    states = tuple(
        _document_state(project_root, relative_path, heading)
        for relative_path, heading in REQUIRED_DOCUMENTS
    )
    return DocumentationStatus(
        states.count("valid"),
        states.count("missing"),
        states.count("invalid"),
    )


def _document_state(root: Path, relative_path: Path, heading: str) -> str:
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return "invalid"
    if not path.exists():
        return "missing"
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_DOCUMENT_BYTES:
        return "invalid"
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return "invalid"
    return "valid" if content.splitlines()[:1] == [heading] else "invalid"


def _validate_status(status: DocumentationStatus) -> None:
    if not isinstance(status, DocumentationStatus):
        raise TypeError("Documentation status reader returned an invalid value.")
    counts = (status.valid, status.missing, status.invalid)
    if not all(type(value) is int and value >= 0 for value in counts):
        raise ValueError("Documentation status counts must be non-negative integers.")
    if sum(counts) != DOCUMENT_COUNT:
        raise ValueError("Documentation status count does not match the allowlist.")


def _spoken_status(status: DocumentationStatus) -> str:
    if status.valid == DOCUMENT_COUNT:
        return (
            "Die feste Projektdokumentation ist vollständig. "
            f"Alle {DOCUMENT_COUNT} geprüften Dokumente sind gültig."
        )
    return (
        "Die feste Projektdokumentation ist unvollständig. "
        f"{_count(status.valid, 'Dokument ist', 'Dokumente sind')} gültig. "
        f"{_count(status.missing, 'Dokument fehlt', 'Dokumente fehlen')}. "
        f"{_count(status.invalid, 'Dokument ist', 'Dokumente sind')} ungültig."
    )


def _count(value: int, singular: str, plural: str) -> str:
    return f"{value} {singular if value == 1 else plural}"
