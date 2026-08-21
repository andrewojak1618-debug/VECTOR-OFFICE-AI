"""Read one strictly bounded stable Python version from Python.org."""

import re
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from tools.permissions import PermissionLevel
from tools.registry import ToolArguments, ToolDefinition, ToolOutput, ToolRegistry
from tools.research_source import (
    PYTHON_SOURCE_LABEL,
    PYTHON_SOURCE_URL,
    SOURCE_TIMEOUT_SECONDS,
    SOURCE_USER_AGENT,
)


MAX_RESPONSE_BYTES = 750_000
VERSION_PATTERN = re.compile(
    r"\bPython (3\.[0-9]{1,2}\.[0-9]{1,3})(?![0-9A-Za-z])"
)
PythonVersionReader = Callable[[], str | None]


@dataclass(frozen=True)
class FixedPythonLatestVersionTool:
    """Return only a validated stable version from the fixed official page."""

    reader: PythonVersionReader

    @property
    def definition(self) -> ToolDefinition:
        """Describe the argument-free, network-authorized version query."""
        return ToolDefinition(
            name="research.python_latest_version",
            description="Read the latest stable Python version from Python.org.",
            permission=PermissionLevel.NETWORK,
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Reduce the remote result to a strict version or safe absence."""
        version = self.reader()
        if version is None:
            return {
                "source": PYTHON_SOURCE_LABEL,
                "status": "unavailable",
                "version": "",
                "spoken_text": (
                    "Die aktuelle Python-Version konnte nicht sicher geprüft werden."
                ),
            }
        if not _is_stable_version(version):
            raise ValueError("Python version reader returned invalid data.")
        return {
            "source": PYTHON_SOURCE_LABEL,
            "status": "verified",
            "version": version,
            "spoken_text": _spoken_version(version),
        }


def register_python_latest_version_tool(
    registry: ToolRegistry,
    reader: PythonVersionReader | None = None,
) -> None:
    """Register the fixed query without user-controlled network parameters."""
    registry.register(FixedPythonLatestVersionTool(
        reader or _read_latest_stable_version,
    ))


def _read_latest_stable_version() -> str | None:
    body = _download_bounded_page()
    if body is None:
        return None
    try:
        page = body.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return _extract_latest_stable_version(page)


def _download_bounded_page() -> bytes | None:
    try:
        with httpx.Client(
            headers={"User-Agent": SOURCE_USER_AGENT},
            timeout=SOURCE_TIMEOUT_SECONDS,
            follow_redirects=False,
        ) as client:
            with client.stream("GET", PYTHON_SOURCE_URL) as response:
                if not _is_html_response(response):
                    return None
                return _read_limited_bytes(response)
    except httpx.HTTPError:
        return None


def _is_html_response(response: httpx.Response) -> bool:
    content_type = response.headers.get("content-type", "")
    media_type = content_type.partition(";")[0].casefold().strip()
    return response.status_code == httpx.codes.OK and media_type == "text/html"


def _read_limited_bytes(response: httpx.Response) -> bytes | None:
    chunks = []
    size = 0
    for chunk in response.iter_bytes():
        size += len(chunk)
        if size > MAX_RESPONSE_BYTES:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def _extract_latest_stable_version(page: str) -> str | None:
    """Extract the numerically newest final release and reject prereleases."""
    versions = {
        match.group(1)
        for match in VERSION_PATTERN.finditer(page)
        if _is_stable_version(match.group(1))
    }
    if not versions:
        return None
    return max(versions, key=lambda item: tuple(map(int, item.split("."))))


def _is_stable_version(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(
        r"3\.[0-9]{1,2}\.[0-9]{1,3}",
        value,
    ) is not None


def _spoken_version(version: str) -> str:
    spoken = " Punkt ".join(version.split("."))
    return f"Laut Python.org ist die aktuelle stabile Version Python {spoken}."
