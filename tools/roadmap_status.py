"""Expose the next fixed local roadmap item as a read-only tool."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tools.permissions import PermissionLevel
from tools.registry import ToolArguments, ToolDefinition, ToolOutput, ToolRegistry


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROADMAP_PATH = Path("docs/roadmap.md")
TOOLS_SECTION = "## Tools und Sicherheit"
PENDING_PREFIX = "- ⏳ "
MAX_ROADMAP_BYTES = 64_000
MAX_ITEM_LENGTH = 180
SAFE_ITEM_PATTERN = re.compile(
    r"^[A-Za-zÄÖÜäöüß0-9 ,.:;()'„“”!?-]{1,180}$",
)


RoadmapReader = Callable[[Path], str | None]


@dataclass(frozen=True)
class NextRoadmapItemTool:
    """Return one validated item from the fixed tools roadmap section."""

    project_root: Path = PROJECT_ROOT
    reader: RoadmapReader | None = None

    def __post_init__(self) -> None:
        if self.reader is None:
            object.__setattr__(self, "reader", _read_next_tools_item)

    @property
    def definition(self) -> ToolDefinition:
        """Describe the argument-free local roadmap lookup."""
        return ToolDefinition(
            name="development.next_roadmap_item",
            description="Return the next pending item from the fixed local roadmap.",
            permission=PermissionLevel.READ_ONLY,
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Read and validate one non-sensitive roadmap summary."""
        item = self.reader(self.project_root.resolve())
        if item is not None:
            _validate_item(item)
        return {
            "found": item is not None,
            "next_item": item or "",
            "spoken_text": _spoken_item(item),
        }


def register_next_roadmap_item_tool(
    registry: ToolRegistry,
    project_root: Path = PROJECT_ROOT,
    reader: RoadmapReader | None = None,
) -> None:
    """Register the fixed argument-free roadmap lookup."""
    registry.register(NextRoadmapItemTool(project_root, reader))


def _read_next_tools_item(project_root: Path) -> str | None:
    roadmap = (project_root / ROADMAP_PATH).resolve()
    _ensure_local_roadmap(project_root, roadmap)
    lines = roadmap.read_text(encoding="utf-8").splitlines()
    in_section = False
    for line in lines:
        if line == TOOLS_SECTION:
            in_section = True
            continue
        if in_section and line.startswith("## "):
            return None
        if in_section and line.startswith(PENDING_PREFIX):
            return line.removeprefix(PENDING_PREFIX).strip()
    return None


def _ensure_local_roadmap(project_root: Path, roadmap: Path) -> None:
    try:
        roadmap.relative_to(project_root.resolve())
    except ValueError as error:
        raise OSError("Fixed roadmap is outside the project root.") from error
    if not roadmap.is_file() or roadmap.stat().st_size > MAX_ROADMAP_BYTES:
        raise OSError("Fixed roadmap is unavailable or too large.")


def _validate_item(item: str) -> None:
    if not isinstance(item, str):
        raise TypeError("Roadmap reader returned an invalid value.")
    if len(item) > MAX_ITEM_LENGTH or SAFE_ITEM_PATTERN.fullmatch(item) is None:
        raise ValueError("Roadmap item contains unsupported content.")


def _spoken_item(item: str | None) -> str:
    if item is None:
        return "Im Bereich Tools und Sicherheit ist kein offener Punkt eingetragen."
    return f"Der nächste offene Projektpunkt lautet: {item.rstrip('.')}."
