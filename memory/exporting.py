"""Secret-aware JSON exports for local library and memory metadata."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from memory.models import (
    DocumentIndexStatus,
    KnowledgeDocumentVersion,
    MemoryEntry,
)


EXPORT_SCHEMA_VERSION = 1
REDACTED = "[REDACTED]"
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{8,}"),
    re.compile(
        r"(?i)\b(api[_ -]?key|password|secret|token)\b"
        r"(\s*[:=]\s*)([^\s,;]+)"
    ),
)


def redact_secrets(value: str) -> str:
    """Replace common credential forms without logging the original value."""
    redacted = SECRET_PATTERNS[0].sub(REDACTED, value)
    redacted = SECRET_PATTERNS[1].sub(f"Bearer {REDACTED}", redacted)
    return SECRET_PATTERNS[2].sub(rf"\1\2{REDACTED}", redacted)


class LocalDataExporter:
    """Write separate sanitized JSON exports with atomic replacement."""

    def export_library(
        self,
        destination: str | Path,
        statuses: Sequence[DocumentIndexStatus],
        versions: Mapping[int, Sequence[KnowledgeDocumentVersion]],
    ) -> Path:
        """Export document, version, and index metadata without source text."""
        documents = tuple(
            self._document_payload(status, versions.get(status.document.id, ()))
            for status in statuses
        )
        return self._write(
            destination,
            "vector-office-ai-library-metadata",
            {"documents": documents},
        )

    def export_memories(
        self,
        destination: str | Path,
        memories: Sequence[MemoryEntry],
    ) -> Path:
        """Export confirmed memories separately with credential redaction."""
        entries = tuple(
            {
                "id": memory.id,
                "content": memory.content,
                "category": memory.category,
                "source": memory.source,
                "created_at": memory.created_at,
            }
            for memory in memories
        )
        return self._write(
            destination,
            "vector-office-ai-confirmed-memories",
            {"memories": entries},
        )

    @staticmethod
    def _document_payload(
        status: DocumentIndexStatus,
        versions: Sequence[KnowledgeDocumentVersion],
    ) -> dict[str, Any]:
        document = status.document
        return {
            "id": document.id,
            "title": document.title,
            "source_name": Path(document.source_path).name,
            "content_hash": document.content_hash,
            "imported_at": document.imported_at,
            "version_count": status.version_count,
            "chunk_count": status.chunk_count,
            "embedding": {
                "model_name": status.model_name,
                "model_version": status.model_version,
                "dimension": status.dimension,
                "current_vectors": status.current_vectors,
                "stale_vectors": status.stale_vectors,
            },
            "versions": tuple(LocalDataExporter._version_payload(item) for item in versions),
        }

    @staticmethod
    def _version_payload(version: KnowledgeDocumentVersion) -> dict[str, Any]:
        return {
            "version": version.version_number,
            "content_hash": version.content_hash,
            "chunk_count": version.chunk_count,
            "imported_at": version.imported_at,
        }

    def _write(
        self,
        destination: str | Path,
        export_type: str,
        content: Mapping[str, Any],
    ) -> Path:
        path = self._resolve_destination(destination)
        payload = {
            "export_type": export_type,
            "schema_version": EXPORT_SCHEMA_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            **content,
        }
        encoded = json.dumps(self._sanitize(payload), ensure_ascii=False, indent=2)
        self._atomic_write(path, f"{encoded}\n")
        return path

    @staticmethod
    def _resolve_destination(destination: str | Path) -> Path:
        path = Path(str(destination).strip().strip('"')).expanduser().resolve()
        if path.suffix.casefold() != ".json":
            raise ValueError("Export destination must be a JSON file.")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _sanitize(value: Any) -> Any:
        if isinstance(value, str):
            return redact_secrets(value)
        if isinstance(value, Mapping):
            return {key: LocalDataExporter._sanitize(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [LocalDataExporter._sanitize(item) for item in value]
        return value

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        temporary = path.with_name(f".{path.name}.tmp")
        try:
            temporary.write_text(content, encoding="utf-8")
            temporary.replace(path)
        finally:
            if temporary.exists():
                temporary.unlink()
