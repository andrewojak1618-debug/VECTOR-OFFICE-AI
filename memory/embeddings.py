"""Generate local document embeddings through the Ollama provider."""

from typing import Any, Sequence

import httpx

from memory.embedding_types import (
    EmbeddingError,
    EmbeddingModelInfo,
    EmbeddingModelUnavailableError,
    EmbeddingProvider,
    EmbeddingResult,
    EmbeddingText,
    EmbeddingVector,
)


OLLAMA_EMBED_ENDPOINT = "/api/embed"
OLLAMA_SHOW_ENDPOINT = "/api/show"
OLLAMA_TAGS_ENDPOINT = "/api/tags"


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
        """Initialisiert den lokalen Ollama-Adapter mit Modell- und Zeitgrenzen."""
        self._model_name = self._require_text(model_name, "model name")
        self.expected_dimension = self._validate_dimension(expected_dimension)
        self._observed_dimension: int | None = None
        self._model_version: str | None = None
        if timeout <= 0:
            raise ValueError("Embedding timeout must be greater than zero.")
        self.timeout = timeout
        self.client = client or httpx.Client(
            base_url=self._require_text(base_url, "Ollama host").rstrip("/"),
            timeout=timeout,
        )

    @property
    def model_name(self) -> str:
        """Liefert das konfigurierte lokale Ollama-Einbettungsmodell."""
        return self._model_name

    @property
    def dimension(self) -> int | None:
        """Liefert die beobachtete Dimension oder deren konfigurierte Erwartung."""
        return self._observed_dimension or self.expected_dimension

    @property
    def model_version(self) -> str | None:
        """Liefert den Hash des installierten Ollama-Modells, sofern bekannt."""
        return self._model_version

    def ensure_model_available(self) -> EmbeddingModelInfo:
        """Prüft Ollama-Modellmetadaten, ohne Dokumentinhalte zu senden."""
        try:
            response = self.client.post(
                OLLAMA_SHOW_ENDPOINT,
                json={"model": self.model_name, "verbose": False},
            )
            self._raise_for_model_status(response)
        except httpx.HTTPError:
            raise EmbeddingError(
                "Local Ollama is unavailable. Check service and timeout."
            ) from None
        metadata_dimension = self._metadata_dimension(response)
        if metadata_dimension is not None:
            self._register_dimension(metadata_dimension)
        self._model_version = self._load_model_version()
        return EmbeddingModelInfo(
            self.model_name,
            self._model_version,
            self.dimension,
        )

    def embed(self, text: EmbeddingText) -> EmbeddingResult:
        """Erzeugt einen lokalen Vektor über den gemeinsamen Stapelpfad."""
        return self.embed_many((text,))[0]

    def embed_many(
        self,
        texts: Sequence[EmbeddingText],
    ) -> tuple[EmbeddingResult, ...]:
        """Erzeugt geordnete Vektoren für mehrere Abschnitte in einer Anfrage."""
        normalized_texts = tuple(texts)
        self._validate_texts(normalized_texts)
        response = self._request_embeddings(normalized_texts)
        results = self._parse_results(normalized_texts, response)
        self._register_batch_dimension(results)
        return results

    def _request_embeddings(
        self,
        texts: tuple[EmbeddingText, ...],
    ) -> httpx.Response:
        """Sendet Dokumenttexte ausschließlich an den lokalen Einbettungsendpunkt."""
        values = [text.value for text in texts]
        payload: dict[str, Any] = {
            "model": self.model_name,
            "input": values[0] if len(values) == 1 else values,
            "truncate": False,
        }
        if self.expected_dimension is not None:
            payload["dimensions"] = self.expected_dimension
        try:
            response = self.client.post(OLLAMA_EMBED_ENDPOINT, json=payload)
            self._raise_for_model_status(response)
            return response
        except httpx.HTTPError:
            raise EmbeddingError(
                "Local Ollama embedding failed. Check service and timeout."
            ) from None

    def _parse_results(
        self,
        texts: tuple[EmbeddingText, ...],
        response: httpx.Response,
    ) -> tuple[EmbeddingResult, ...]:
        """Validiert und überführt eine Ollama-Antwort in geordnete Ergebnisse."""
        try:
            payload = response.json()
            model_name = self._response_model(payload)
            vectors = self._response_vectors(payload, len(texts))
            return tuple(
                EmbeddingResult(text, vector, model_name)
                for text, vector in zip(texts, vectors)
            )
        except (KeyError, TypeError, ValueError):
            raise EmbeddingError(
                "Local Ollama returned an invalid embedding response."
            ) from None

    def _register_batch_dimension(
        self,
        results: tuple[EmbeddingResult, ...],
    ) -> None:
        """Verlangt für einen Stapel genau eine einheitliche Vektordimension."""
        dimensions = {result.dimension for result in results}
        if len(dimensions) != 1:
            raise EmbeddingError(
                "Local Ollama returned inconsistent embedding dimensions."
            )
        self._register_dimension(dimensions.pop())

    def _register_dimension(self, dimension: int) -> None:
        """Registriert eine Dimension und blockiert unerwartete Änderungen."""
        if self.expected_dimension not in (None, dimension):
            raise EmbeddingError(
                "Local Ollama returned an unexpected embedding dimension."
            )
        if self._observed_dimension not in (None, dimension):
            raise EmbeddingError(
                "Local Ollama embedding dimension changed unexpectedly."
            )
        self._observed_dimension = dimension

    def _raise_for_model_status(self, response: httpx.Response) -> None:
        """Unterscheidet ein fehlendes lokales Modell von anderen HTTP-Fehlern."""
        if response.status_code == httpx.codes.NOT_FOUND:
            raise EmbeddingModelUnavailableError(
                f"Local embedding model '{self.model_name}' is not installed. "
                f"Run: ollama pull {self.model_name}"
            )
        response.raise_for_status()

    def _load_model_version(self) -> str:
        """Liest den installierten Modellhash aus der lokalen Ollama-Liste."""
        try:
            response = self.client.get(OLLAMA_TAGS_ENDPOINT)
            response.raise_for_status()
            models = response.json()["models"]
            matching = next(
                model for model in models if self._matches_model(model.get("name"))
            )
            digest = matching["digest"]
        except (httpx.HTTPError, KeyError, StopIteration, TypeError, ValueError):
            raise EmbeddingError(
                "Local Ollama model version could not be determined."
            ) from None
        return self._require_text(digest, "model version")

    def _matches_model(self, installed_name: object) -> bool:
        """Vergleicht Modellnamen unter kontrollierter Berücksichtigung von `latest`."""
        if not isinstance(installed_name, str):
            return False
        if installed_name == self.model_name:
            return True
        return ":" not in self.model_name and installed_name == (
            f"{self.model_name}:latest"
        )

    @staticmethod
    def _metadata_dimension(response: httpx.Response) -> int | None:
        """Extrahiert eine positive Einbettungsdimension aus Modellmetadaten."""
        try:
            model_info = response.json().get("model_info", {})
        except (AttributeError, ValueError):
            return None
        if not isinstance(model_info, dict):
            return None
        candidates = (
            value
            for key, value in model_info.items()
            if key.endswith(".embedding_length")
        )
        dimension = next(candidates, None)
        return dimension if isinstance(dimension, int) and dimension > 0 else None

    @staticmethod
    def _response_model(payload: dict[str, Any]) -> str:
        """Extrahiert einen gültigen Modellnamen aus der Antwort."""
        model_name = payload["model"]
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("Invalid response model.")
        return model_name

    @staticmethod
    def _response_vectors(
        payload: dict[str, Any],
        expected_count: int,
    ) -> tuple[EmbeddingVector, ...]:
        """Validiert Anzahl und Struktur der zurückgegebenen Vektoren."""
        embeddings = payload["embeddings"]
        if not isinstance(embeddings, list) or len(embeddings) != expected_count:
            raise ValueError("Unexpected embedding count.")
        if not all(isinstance(values, list) for values in embeddings):
            raise ValueError("Embedding values must be lists.")
        return tuple(EmbeddingVector(tuple(values)) for values in embeddings)

    @staticmethod
    def _validate_texts(texts: tuple[EmbeddingText, ...]) -> None:
        """Verlangt mindestens einen ausschließlich normalisierten Einbettungstext."""
        if not texts:
            raise ValueError("At least one embedding text is required.")
        if not all(isinstance(text, EmbeddingText) for text in texts):
            raise TypeError("embed_many() requires EmbeddingText values.")

    @staticmethod
    def _validate_dimension(dimension: int | None) -> int | None:
        """Akzeptiert nur eine positive oder unbekannte Vektordimension."""
        if dimension is not None and dimension < 1:
            raise ValueError("Embedding dimension must be at least one.")
        return dimension

    @staticmethod
    def _require_text(value: str, label: str) -> str:
        """Normalisiert ein verpflichtendes nicht leeres Textfeld."""
        if not isinstance(value, str):
            raise TypeError(f"Embedding {label} must be a string.")
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"Embedding {label} must not be empty.")
        return normalized


def create_embedding_provider(settings) -> EmbeddingProvider:
    """Erzeugt ausschließlich den konfigurierten lokalen Einbettungsanbieter."""
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
