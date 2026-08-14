"""Validate, read, fingerprint, and segment deliberately selected documents."""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PreparedDocument:
    """Contain normalized metadata and sections ready for SQLite import."""

    path: Path
    source: str
    title: str
    content_hash: str
    chunks: tuple[str, ...]


class DocumentTextProcessor:
    """Apply bounded UTF-8 file validation and deterministic segmentation."""

    ALLOWED_EXTENSIONS = frozenset({".md", ".txt"})
    DEFAULT_MAX_FILE_BYTES = 2 * 1024 * 1024
    DEFAULT_CHUNK_SIZE = 1000
    MIN_CHUNK_SIZE = 100

    def __init__(self, max_file_bytes: int, chunk_size: int):
        self._validate_limits(max_file_bytes, chunk_size)
        self.max_file_bytes = max_file_bytes
        self.chunk_size = chunk_size

    def prepare(self, source_path: str | Path) -> PreparedDocument:
        """Validate and transform one selected document without persisting it."""
        path = self._resolve_path(source_path)
        content = self._read(path)
        normalized = content.strip()
        if not normalized:
            raise ValueError("Document must not be empty.")
        return PreparedDocument(
            path=path,
            source=str(path),
            title=path.stem,
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            chunks=self.split(normalized),
        )

    def split(self, content: str) -> tuple[str, ...]:
        """Split normalized text into stable bounded sections."""
        chunks: list[str] = []
        current = ""
        for paragraph in re.split(r"\n\s*\n", content):
            for part in self._split_long_paragraph(paragraph.strip()):
                current = self._append_part(chunks, current, part)
        if current:
            chunks.append(current)
        return tuple(chunks)

    @classmethod
    def _validate_limits(cls, max_file_bytes: int, chunk_size: int) -> None:
        if max_file_bytes < 1:
            raise ValueError("Maximum file size must be at least 1 byte.")
        if chunk_size < cls.MIN_CHUNK_SIZE:
            raise ValueError("Chunk size must be at least 100 characters.")

    def _resolve_path(self, source_path: str | Path) -> Path:
        path_text = str(source_path).strip().strip('"')
        path = Path(path_text).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"Document does not exist: {path}")
        if path.suffix.casefold() not in self.ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(self.ALLOWED_EXTENSIONS))
            raise ValueError(f"Only these document types are allowed: {allowed}")
        if path.stat().st_size > self.max_file_bytes:
            raise ValueError(f"Document exceeds the {self.max_file_bytes}-byte limit.")
        return path

    @staticmethod
    def _read(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Document must be UTF-8 encoded.") from exc

    def _append_part(self, chunks: list[str], current: str, part: str) -> str:
        if not part:
            return current
        candidate = f"{current}\n\n{part}" if current else part
        if len(candidate) <= self.chunk_size:
            return candidate
        chunks.append(current)
        return part

    def _split_long_paragraph(self, paragraph: str) -> tuple[str, ...]:
        if not paragraph or len(paragraph) <= self.chunk_size:
            return (paragraph,) if paragraph else ()
        parts: list[str] = []
        current = ""
        for word in paragraph.split():
            if len(word) > self.chunk_size:
                current = self._append_long_word(parts, current, word)
                continue
            current = self._append_word(parts, current, word)
        if current:
            parts.append(current)
        return tuple(parts)

    def _append_long_word(self, parts: list[str], current: str, word: str) -> str:
        if current:
            parts.append(current)
        parts.extend(
            word[index:index + self.chunk_size]
            for index in range(0, len(word), self.chunk_size)
        )
        return ""

    def _append_word(self, parts: list[str], current: str, word: str) -> str:
        candidate = f"{current} {word}" if current else word
        if len(candidate) <= self.chunk_size:
            return candidate
        parts.append(current)
        return word
