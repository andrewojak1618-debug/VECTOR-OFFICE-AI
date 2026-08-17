"""Language-model adapters and provider composition."""

from typing import Any, Sequence

import httpx
from openai import OpenAI, OpenAIError

from brain.agent import LanguageModel
from brain.context import ChatMessage


def _message_payload(messages: Sequence[ChatMessage]) -> list[dict[str, str]]:
    return [
        {"role": message.role, "content": message.content}
        for message in messages
    ]


class OpenAIProvider:
    """Generate responses through the OpenAI Responses API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        client: Any | None = None,
    ):
        if not api_key.strip():
            raise ValueError("OPENAI_API_KEY is required for the OpenAI provider.")
        if not model.strip():
            raise ValueError("OPENAI_MODEL must not be empty.")
        self.model = model
        self.client = client or OpenAI(api_key=api_key)

    def generate(self, messages: Sequence[ChatMessage]) -> str:
        """Return one model response without exposing provider exceptions."""
        try:
            response = self.client.responses.create(
                model=self.model,
                input=_message_payload(messages),
            )
        except OpenAIError:
            raise RuntimeError(
                "OpenAI request failed. Check API key, model access, and billing."
            ) from None
        return response.output_text


class OllamaProvider:
    """Generate responses through a local Ollama chat endpoint."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = 120.0,
        temperature: float | None = None,
        client: httpx.Client | None = None,
    ):
        if not base_url.strip():
            raise ValueError("OLLAMA_HOST must not be empty.")
        if not model.strip():
            raise ValueError("OLLAMA_MODEL must not be empty.")
        if temperature is not None and not 0.0 <= temperature <= 2.0:
            raise ValueError("Ollama temperature must be between 0 and 2.")
        self.model = model
        self.temperature = temperature
        self.client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
        )

    def generate(self, messages: Sequence[ChatMessage]) -> str:
        """Return one local response and sanitize transport failures."""
        try:
            response = self.client.post(
                "/api/chat",
                json=self._request_payload(messages),
            )
            response.raise_for_status()
        except httpx.HTTPError:
            raise RuntimeError(
                "Ollama request failed. Check service, host, and model."
            ) from None
        return self._response_content(response)

    def _request_payload(self, messages: Sequence[ChatMessage]) -> dict:
        payload = {
            "model": self.model,
            "messages": _message_payload(messages),
            "stream": False,
        }
        if self.temperature is not None:
            payload["options"] = {"temperature": self.temperature}
        return payload

    @staticmethod
    def _response_content(response: httpx.Response) -> str:
        content = response.json().get("message", {}).get("content", "")
        if not isinstance(content, str):
            raise RuntimeError("Ollama returned an invalid response.")
        return content


class FallbackProvider:
    """Use a secondary model only when the primary model is unavailable."""

    def __init__(self, primary: LanguageModel, fallback: LanguageModel):
        self.primary = primary
        self.fallback = fallback

    def generate(self, messages: Sequence[ChatMessage]) -> str:
        """Return the primary response or deliberately use the fallback."""
        content = self._try_primary(messages)
        if content:
            return content
        print("OpenAI unavailable. Using local Ollama fallback.")
        return self._generate_fallback(messages)

    def _try_primary(self, messages: Sequence[ChatMessage]) -> str:
        try:
            return self.primary.generate(messages).strip()
        except RuntimeError:
            return ""

    def _generate_fallback(self, messages: Sequence[ChatMessage]) -> str:
        try:
            return self.fallback.generate(messages)
        except RuntimeError:
            raise RuntimeError(
                "OpenAI and the local Ollama fallback both failed."
            ) from None


def create_language_model(settings) -> LanguageModel:
    """Build the configured language model and optional local fallback."""
    provider = settings.LLM_PROVIDER.casefold().strip()
    if provider == "openai":
        return _create_openai_model(settings)
    if provider == "ollama":
        return _create_ollama_model(settings)
    raise ValueError("LLM_PROVIDER must be either 'openai' or 'ollama'.")


def _create_openai_model(settings) -> LanguageModel:
    primary = OpenAIProvider(settings.OPENAI_API_KEY, settings.OPENAI_MODEL)
    fallback = settings.LLM_FALLBACK_PROVIDER.casefold().strip()
    if fallback == "none":
        return primary
    if fallback == "ollama":
        return FallbackProvider(primary, _create_ollama_model(settings))
    raise ValueError("LLM_FALLBACK_PROVIDER must be either 'ollama' or 'none'.")


def _create_ollama_model(settings) -> OllamaProvider:
    return OllamaProvider(settings.OLLAMA_HOST, settings.OLLAMA_MODEL)
