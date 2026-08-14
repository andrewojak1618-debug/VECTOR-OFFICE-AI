"""Provider-neutral types and local Ollama embedding generation."""

import math
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import httpx


OLLAMA_EMBED_ENDPOINT = "/api/embed"


class EmbeddingError(RuntimeError):
    """Report a safe, understandable local embedding failure."""


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
        normalized_model = self.model_name.strip()
        if not normalized_model:
            raise ValueError("Embedding model name must not be empty.")
        object.__setattr__(self, "model_name", normalized_model)

    @property
    def dimension(self) -> int:
        """Return the actual vector dimension reported by its values."""
        return self.vector.dimension


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Generate semantic vectors without coupling callers to one service."""

    @property
    def model_name(self) -> str:
        """Return the configured embedding model identifier."""
        ...

    def embed(self, text: EmbeddingText) -> EmbeddingResult:
        """Generate one embedding for a normalized text input."""
        ...


class OllamaEmbeddingProvider:
    """Generate embeddings through Ollama's local `/api/embed` endpoint."""

    def __init__(
        self,
        base_url: str,
        model_name: str,
        expected_dimension: int | None = None,
        timeout: float = 60.0,
        client: httpx.Client | None = None,
    ):
        self._model_name = self._require_text(model_name, "model name")
        self.expected_dimension = self._validate_dimension(expected_dimension)
        if timeout <= 0:
            raise ValueError("Embedding timeout must be greater than zero.")
        self.timeout = timeout
        self.client = client or httpx.Client(
            base_url=self._require_text(base_url, "Ollama host").rstrip("/"),
            timeout=timeout,
        )

    @property
    def model_name(self) -> str:
        """Return the configured local Ollama embedding model."""
        return self._model_name

    def embed(self, text: EmbeddingText) -> EmbeddingResult:
        """Generate one local vector and validate model and dimension metadata."""
        if not isinstance(text, EmbeddingText):
            raise TypeError("embed() requires an EmbeddingText value.")
        response = self._request_embedding(text)
        result = self._parse_result(text, response)
        self._require_expected_dimension(result.dimension)
        return result

    def _request_embedding(self, text: EmbeddingText) -> httpx.Response:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "input": text.value,
            "truncate": False,
        }
        if self.expected_dimension is not None:
            payload["dimensions"] = self.expected_dimension
        try:
            response = self.client.post(OLLAMA_EMBED_ENDPOINT, json=payload)
            response.raise_for_status()
            return response
        except httpx.HTTPError:
            raise EmbeddingError(
                "Local Ollama embedding failed. Check service, model, and timeout."
            ) from None

    def _parse_result(
        self,
        text: EmbeddingText,
        response: httpx.Response,
    ) -> EmbeddingResult:
        try:
            payload = response.json()
            model_name = self._response_model(payload)
            vector = EmbeddingVector(self._response_values(payload))
        except (KeyError, TypeError, ValueError):
            raise EmbeddingError(
                "Local Ollama returned an invalid embedding response."
            ) from None
        return EmbeddingResult(text, vector, model_name)

    @staticmethod
    def _response_model(payload: dict[str, Any]) -> str:
        model_name = payload["model"]
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("Invalid response model.")
        return model_name

    @staticmethod
    def _response_values(payload: dict[str, Any]) -> tuple[float, ...]:
        embeddings = payload["embeddings"]
        if not isinstance(embeddings, list) or len(embeddings) != 1:
            raise ValueError("Expected exactly one embedding.")
        if not isinstance(embeddings[0], list):
            raise ValueError("Embedding values must be a list.")
        return tuple(embeddings[0])

    def _require_expected_dimension(self, actual_dimension: int) -> None:
        if (
            self.expected_dimension is not None
            and actual_dimension != self.expected_dimension
        ):
            raise EmbeddingError(
                "Local Ollama returned an unexpected embedding dimension."
            )

    @staticmethod
    def _validate_dimension(dimension: int | None) -> int | None:
        if dimension is not None and dimension < 1:
            raise ValueError("Embedding dimension must be at least one.")
        return dimension

    @staticmethod
    def _require_text(value: str, label: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"Embedding {label} must not be empty.")
        return normalized


def create_embedding_provider(settings) -> EmbeddingProvider:
    """Build the configured local provider; cloud providers are unsupported."""
    provider_name = settings.EMBEDDING_PROVIDER.casefold().strip()
    if provider_name != "ollama":
        raise ValueError("EMBEDDING_PROVIDER must be 'ollama' (local only).")
    configured_dimension = settings.OLLAMA_EMBEDDING_DIMENSION
    expected_dimension = configured_dimension or None
    return OllamaEmbeddingProvider(
        base_url=settings.OLLAMA_HOST,
        model_name=settings.OLLAMA_EMBEDDING_MODEL,
        expected_dimension=expected_dimension,
        timeout=settings.OLLAMA_EMBEDDING_TIMEOUT,
    )
