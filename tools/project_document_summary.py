"""Fasst ausschließlich fest freigegebene Projektdokumente lokal zusammen."""

from collections.abc import Callable
from dataclasses import dataclass
import re
from pathlib import Path

from brain.reflection import ResponseQualityPolicy
from brain.response_quality import ProviderResponsePolicy
from tools.permissions import PermissionLevel
from tools.project_documents import (
    PROJECT_ROOT,
    read_approved_project_document,
)
from tools.registry import (
    ToolArguments,
    ToolDefinition,
    ToolOutput,
    ToolParameter,
    ToolParameterType,
    ToolRegistry,
)


MAX_SUMMARY_LENGTH = 420
UNSAFE_SUMMARY_PATTERN = re.compile(r"https?://|[A-Za-z]:\\|\.\./|\.\.\\")
DocumentSummarizer = Callable[[str, str], str]


@dataclass(frozen=True)
class ProjectDocumentSummaryTool:
    """Liest ein festes Dokument und liefert eine geprüfte lokale Kurzfassung."""

    project_root: Path = PROJECT_ROOT
    summarizer: DocumentSummarizer | None = None

    def __post_init__(self) -> None:
        """Setzt bei fehlender lokaler Modellabhängigkeit einen sicheren Fehlerpfad."""
        if self.summarizer is None:
            object.__setattr__(self, "summarizer", _unavailable_summarizer)

    @property
    def definition(self) -> ToolDefinition:
        """Beschreibt die rein lesende Zusammenfassung einer festen Dokument-ID."""
        return ToolDefinition(
            name="development.summarize_project_document",
            description="Summarize one fixed approved project document locally.",
            permission=PermissionLevel.READ_ONLY,
            parameters=(ToolParameter(
                "document_id",
                "Exact identifier from the fixed project document allowlist.",
                ToolParameterType.STRING,
            ),),
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Liest die feste Freigabe und gibt nur zwei geprüfte lokale Sätze zurück."""
        document, content = read_approved_project_document(
            self.project_root,
            str(arguments["document_id"]),
        )
        summary = _validated_summary(
            self.summarizer(document.display_name, content)
        )
        return {
            "document_id": document.identifier,
            "display_name": document.display_name,
            "summary": summary,
            "spoken_text": f"{document.display_name}: {summary}",
        }


def register_project_document_summary_tool(
    registry: ToolRegistry,
    project_root: Path = PROJECT_ROOT,
    summarizer: DocumentSummarizer | None = None,
) -> None:
    """Registriert die lokale Zusammenfassung fest freigegebener Dokumente."""
    registry.register(ProjectDocumentSummaryTool(project_root, summarizer))


def _validated_summary(value: object) -> str:
    """Begrenzt und prüft lokalen Modelltext vor Registry und Sprachausgabe."""
    validated = ProviderResponsePolicy().validate(value, "ollama").text
    summary = ResponseQualityPolicy.limit_sentences(validated, 2)
    if len(summary) > MAX_SUMMARY_LENGTH or UNSAFE_SUMMARY_PATTERN.search(summary):
        raise ValueError("Local document summary contains unsupported content.")
    if ResponseQualityPolicy().issues(summary, 2):
        raise ValueError("Local document summary violates response policy.")
    sentences = re.split(r"(?<=[.!?])\s+", summary)
    if not sentences[0].startswith("Das Dokument beschreibt "):
        raise ValueError("Local document summary has an invalid sentence shape.")
    if len(sentences) == 2 and not sentences[1].startswith("Es nennt "):
        raise ValueError("Local document summary has an invalid sentence shape.")
    return summary


def _unavailable_summarizer(_display_name: str, _content: str) -> str:
    """Meldet eine fehlende lokale Modellabhängigkeit ohne Dokumentinhalt."""
    raise RuntimeError("Local document summarizer is unavailable.")
