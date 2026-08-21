"""Check one fixed external research source behind network authorization."""

from collections.abc import Callable
from dataclasses import dataclass

import httpx

from tools.permissions import PermissionLevel
from tools.registry import ToolArguments, ToolDefinition, ToolOutput, ToolRegistry


PYTHON_SOURCE_URL = "https://www.python.org/downloads/"
PYTHON_SOURCE_LABEL = "Python.org"
SOURCE_TIMEOUT_SECONDS = 5.0
SOURCE_USER_AGENT = "Vector-Office-AI/0.2 research-source-check"
SourceChecker = Callable[[], bool]


@dataclass(frozen=True)
class FixedResearchSourceStatusTool:
    """Return availability for one fixed source without response content."""

    checker: SourceChecker

    @property
    def definition(self) -> ToolDefinition:
        """Describe the argument-free network-authorized source check."""
        return ToolDefinition(
            name="research.python_source_status",
            description="Check availability of the fixed official Python source.",
            permission=PermissionLevel.NETWORK,
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Return one boolean source state without remote body content."""
        available = self.checker()
        if type(available) is not bool:
            raise TypeError("Research source checker must return a boolean.")
        return {
            "source": PYTHON_SOURCE_LABEL,
            "available": available,
            "status": "available" if available else "unavailable",
            "spoken_text": _spoken_status(available),
        }


def register_fixed_research_source_tool(
    registry: ToolRegistry,
    checker: SourceChecker | None = None,
) -> None:
    """Register the fixed external source without user-controlled targets."""
    registry.register(FixedResearchSourceStatusTool(
        checker or _python_source_available,
    ))


def _python_source_available() -> bool:
    try:
        response = httpx.head(
            PYTHON_SOURCE_URL,
            headers={"User-Agent": SOURCE_USER_AGENT},
            timeout=SOURCE_TIMEOUT_SECONDS,
            follow_redirects=False,
        )
    except httpx.HTTPError:
        return False
    return response.status_code == httpx.codes.OK


def _spoken_status(available: bool) -> str:
    if available:
        return "Die fest freigegebene Python-Quelle ist erreichbar."
    return "Die fest freigegebene Python-Quelle ist derzeit nicht erreichbar."
