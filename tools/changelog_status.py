"""Expose one validated latest change from the fixed local changelog."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tools.permissions import PermissionLevel
from tools.registry import ToolArguments, ToolDefinition, ToolOutput, ToolRegistry


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHANGELOG_PATH = Path("CHANGELOG.md")
UNRELEASED_SECTION = "## [Unreleased]"
MAX_CHANGELOG_BYTES = 256_000
MAX_SUMMARY_LENGTH = 180
SAFE_SUMMARY_PATTERN = re.compile(
    r"^[A-Za-zÄÖÜäöüß0-9_ ,.:;()'„“”!?+-]{1,180}$",
)
ChangelogReader = Callable[[Path], str | None]


@dataclass(frozen=True)
class LatestProjectChangeTool:
    """Return the first safe entry from the fixed unreleased section."""

    project_root: Path = PROJECT_ROOT
    reader: ChangelogReader | None = None

    def __post_init__(self) -> None:
        """Setzt den sicheren Standardleser, wenn keiner injiziert wurde."""
        if self.reader is None:
            object.__setattr__(self, "reader", _read_latest_change)

    @property
    def definition(self) -> ToolDefinition:
        """Beschreibt die argumentlose lokale Changelog-Abfrage."""
        return ToolDefinition(
            name="development.latest_change",
            description="Return the latest safe entry from the fixed changelog.",
            permission=PermissionLevel.READ_ONLY,
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Liest eine geprüfte öffentliche Zusammenfassung ohne Modellinterpretation."""
        summary = self.reader(self.project_root.resolve())
        if summary is not None:
            _validate_summary(summary)
        return {
            "found": summary is not None,
            "summary": summary or "",
            "spoken_text": _spoken_summary(summary),
        }


def register_latest_project_change_tool(
    registry: ToolRegistry,
    project_root: Path = PROJECT_ROOT,
    reader: ChangelogReader | None = None,
) -> None:
    """Registriert den festen argumentlosen Changelog-Leser."""
    registry.register(LatestProjectChangeTool(project_root, reader))


def _read_latest_change(project_root: Path) -> str | None:
    """Liest den ersten Eintrag im festen Unreleased-Abschnitt."""
    changelog = (project_root / CHANGELOG_PATH).resolve()
    _ensure_local_changelog(project_root, changelog)
    in_section = False
    for line in changelog.read_text(encoding="utf-8").splitlines():
        if line == UNRELEASED_SECTION:
            in_section = True
            continue
        if in_section and line.startswith("## "):
            return None
        if in_section and line.startswith("- "):
            return line.removeprefix("- ").replace("`", "").strip()
    return None


def _ensure_local_changelog(project_root: Path, changelog: Path) -> None:
    """Begrenzt das Changelog auf die erwartete lokale Projektdatei und Größe."""
    try:
        changelog.relative_to(project_root.resolve())
    except ValueError as error:
        raise OSError("Fixed changelog is outside the project root.") from error
    if not changelog.is_file() or changelog.stat().st_size > MAX_CHANGELOG_BYTES:
        raise OSError("Fixed changelog is unavailable or too large.")


def _validate_summary(summary: str) -> None:
    """Prüft die Zusammenfassung auf Länge, Zeichen und verbotene Ziele."""
    if not isinstance(summary, str):
        raise TypeError("Changelog reader returned an invalid value.")
    forbidden = ("http://", "https://", "/", "\\")
    invalid = any(value in summary.casefold() for value in forbidden)
    if invalid or len(summary) > MAX_SUMMARY_LENGTH:
        raise ValueError("Changelog summary contains unsupported content.")
    if SAFE_SUMMARY_PATTERN.fullmatch(summary) is None:
        raise ValueError("Changelog summary contains unsupported content.")


def _spoken_summary(summary: str | None) -> str:
    """Erzeugt einen lokalen deutschen Sprechtext für den Changelog-Befund."""
    if summary is None:
        return "Im Changelog ist noch keine neue Projektänderung eingetragen."
    return f"Die zuletzt dokumentierte Projektänderung lautet: {summary.rstrip('.')}."
