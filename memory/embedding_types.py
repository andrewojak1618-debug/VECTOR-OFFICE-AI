"""Define provider-neutral text, vector, result, and model contracts."""

import math
from dataclasses import dataclass
from typing import Protocol, Sequence, runtime_checkable


class EmbeddingError(RuntimeError):
    """Report a safe, understandable local embedding failure."""


class EmbeddingModelUnavailableError(EmbeddingError):
    """Report that the configured local embedding model is not installed."""


@dataclass(frozen=True)
class EmbeddingText:
    """One normalized, non-empty text prepared for semantic encoding."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError("Embedding text must be a string.")
        normalized = self.value.strip()
        if not normalized:
            raise ValueError("Embedding text must not be empty.")
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True)
class EmbeddingVector:
    """One immutable, finite, non-empty numeric embedding vector."""

    values: tuple[float, ...]

    def __post_init__(self) -> None:
        raw_values = tuple(self.values)
        if not raw_values:
            raise ValueError("Embedding vector must not be empty.")
        if any(isinstance(value, bool) for value in raw_values):
            raise TypeError("Embedding vector values must be numbers.")
        try:
            normalized = tuple(float(value) for value in raw_values)
        except (TypeError, ValueError) as exc:
            raise TypeError("Embedding vector values must be numbers.") from exc
        if not all(math.isfinite(value) for value in normalized):
            raise ValueError("Embedding vector values must be finite.")
        object.__setattr__(self, "values", normalized)

    @property
    def dimension(self) -> int:
        """Return the number of numeric vector components."""
        return len(self.values)


@dataclass(frozen=True)
class EmbeddingResult:
    """Bind normalized input, vector, model name, and actual dimension."""

    text: EmbeddingText
    vector: EmbeddingVector
    model_name: str

    def __post_init__(self) -> None:
        if not isinstance(self.model_name, str):
            raise TypeError("Embedding model name must be a string.")
        normalized_model = self.model_name.strip()
        if not normalized_model:
            raise ValueError("Embedding model name must not be empty.")
        object.__setattr__(self, "model_name", normalized_model)

    @property
    def dimension(self) -> int:
        """Return the actual vector dimension reported by its values."""
        return self.vector.dimension


@dataclass(frozen=True)
class EmbeddingModelInfo:
    """Describe one installed local embedding model."""

    model_name: str
    model_version: str
    dimension: int | None


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Generate semantic vectors without coupling callers to one service."""

    @property
    def model_name(self) -> str:
        """Return the configured embedding model identifier."""
        ...

    @property
    def dimension(self) -> int | None:
        """Return the expected or observed vector dimension."""
        ...

    @property
    def model_version(self) -> str | None:
        """Return the installed model digest after availability checking."""
        ...

    def ensure_model_available(self) -> EmbeddingModelInfo:
        """Validate that the configured local model is installed."""
        ...

    def embed(self, text: EmbeddingText) -> EmbeddingResult:
        """Generate one embedding for a normalized text input."""
        ...

    def embed_many(
        self,
        texts: Sequence[EmbeddingText],
    ) -> tuple[EmbeddingResult, ...]:
        """Generate embeddings for multiple texts in one provider request."""
        ...
