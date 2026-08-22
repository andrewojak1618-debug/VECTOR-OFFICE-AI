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
        """Beschreibt die argumentlose netzwerkberechtigte Versionsabfrage."""
        return ToolDefinition(
            name="research.python_latest_version",
            description="Read the latest stable Python version from Python.org.",
            permission=PermissionLevel.NETWORK,
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Reduziert das Remote-Ergebnis auf eine strikte Version oder sichere Leere."""
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
    """Registriert die feste Abfrage ohne nutzergesteuerte Netzwerkparameter."""
    registry.register(FixedPythonLatestVersionTool(
        reader or _read_latest_stable_version,
    ))


def _read_latest_stable_version() -> str | None:
    """Lädt die begrenzte Seite und ermittelt daraus die neueste stabile Version."""
    body = _download_bounded_page()
    if body is None:
        return None
    try:
        page = body.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return _extract_latest_stable_version(page)


def _download_bounded_page() -> bytes | None:
    """Lädt nur die feste HTML-Seite und bricht bei Transportfehlern sicher ab."""
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
    """Akzeptiert ausschließlich erfolgreiche Antworten mit HTML-Medientyp."""
    content_type = response.headers.get("content-type", "")
    media_type = content_type.partition(";")[0].casefold().strip()
    return response.status_code == httpx.codes.OK and media_type == "text/html"


def _read_limited_bytes(response: httpx.Response) -> bytes | None:
    """Liest den Antwortstrom nur bis zur festgelegten Bytegrenze."""
    chunks = []
    size = 0
    for chunk in response.iter_bytes():
        size += len(chunk)
        if size > MAX_RESPONSE_BYTES:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def _extract_latest_stable_version(page: str) -> str | None:
    """Ermittelt die numerisch neueste finale Version und verwirft Vorabstände."""
    versions = {
        match.group(1)
        for match in VERSION_PATTERN.finditer(page)
        if _is_stable_version(match.group(1))
    }
    if not versions:
        return None
    return max(versions, key=lambda item: tuple(map(int, item.split("."))))


def _is_stable_version(value: object) -> bool:
    """Prüft einen Wert gegen das erlaubte stabile Python-Versionsformat."""
    return isinstance(value, str) and re.fullmatch(
        r"3\.[0-9]{1,2}\.[0-9]{1,3}",
        value,
    ) is not None


def _spoken_version(version: str) -> str:
    """Formuliert eine validierte Version mit TTS-freundlichen Trennpunkten."""
    spoken = " Punkt ".join(version.split("."))
    return f"Laut Python.org ist die aktuelle stabile Version Python {spoken}."
