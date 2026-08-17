"""Language-model adapters and bounded provider resilience."""

import time
from collections.abc import Callable, Sequence
from typing import Any

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
        timeout: float = 120.0,
        max_attempts: int = 2,
    ):
        if not api_key.strip():
            raise ValueError("OPENAI_API_KEY is required for the OpenAI provider.")
        if not model.strip():
            raise ValueError("OPENAI_MODEL must not be empty.")
        _validate_request_policy(timeout, max_attempts, 0.0)
        self.model = model
        self.client = client or OpenAI(
            api_key=api_key,
            timeout=timeout,
            max_retries=max_attempts - 1,
        )

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
        max_attempts: int = 2,
        retry_delay: float = 0.5,
        temperature: float | None = None,
        client: httpx.Client | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        if not base_url.strip():
            raise ValueError("OLLAMA_HOST must not be empty.")
        if not model.strip():
            raise ValueError("OLLAMA_MODEL must not be empty.")
        if temperature is not None and not 0.0 <= temperature <= 2.0:
            raise ValueError("Ollama temperature must be between 0 and 2.")
        _validate_request_policy(timeout, max_attempts, retry_delay)
        self.model = model
        self.temperature = temperature
        self.max_attempts = max_attempts
        self.retry_delay = retry_delay
        self.sleeper = sleeper
        self.client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
        )

    def generate(self, messages: Sequence[ChatMessage]) -> str:
        """Return one local response and sanitize transport failures."""
        response = self._request(messages)
        return self._response_content(response)

    def _request(self, messages: Sequence[ChatMessage]) -> httpx.Response:
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.client.post(
                    "/api/chat",
                    json=self._request_payload(messages),
                )
                response.raise_for_status()
                return response
            except httpx.HTTPError as exc:
                if not self._may_retry(exc, attempt):
                    break
                self.sleeper(self.retry_delay)
        raise RuntimeError(
            "Ollama request failed. Check service, host, and model."
        ) from None

    def _may_retry(self, error: httpx.HTTPError, attempt: int) -> bool:
        if attempt >= self.max_attempts:
            return False
        if isinstance(error, httpx.RequestError):
            return True
        if isinstance(error, httpx.HTTPStatusError):
            status = error.response.status_code
            return status in {408, 409, 429} or status >= 500
        return False

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
    primary = OpenAIProvider(
        settings.OPENAI_API_KEY,
        settings.OPENAI_MODEL,
        timeout=_request_timeout(settings),
        max_attempts=_max_attempts(settings),
    )
    fallback = settings.LLM_FALLBACK_PROVIDER.casefold().strip()
    if fallback == "none":
        return primary
    if fallback == "ollama":
        return FallbackProvider(primary, _create_ollama_model(settings))
    raise ValueError("LLM_FALLBACK_PROVIDER must be either 'ollama' or 'none'.")


def _create_ollama_model(settings) -> OllamaProvider:
    return OllamaProvider(
        settings.OLLAMA_HOST,
        settings.OLLAMA_MODEL,
        timeout=_request_timeout(settings),
        max_attempts=_max_attempts(settings),
        retry_delay=getattr(settings, "LLM_RETRY_DELAY", 0.5),
    )


def _request_timeout(settings) -> float:
    return getattr(settings, "LLM_REQUEST_TIMEOUT", 120.0)


def _max_attempts(settings) -> int:
    return getattr(settings, "LLM_MAX_ATTEMPTS", 2)


def _validate_request_policy(
    timeout: float,
    max_attempts: int,
    retry_delay: float,
) -> None:
    if not 1.0 <= timeout <= 600.0:
        raise ValueError("LLM request timeout must be between 1 and 600 seconds.")
    if type(max_attempts) is not int or not 1 <= max_attempts <= 5:
        raise ValueError("LLM max attempts must be between 1 and 5.")
    if not 0.0 <= retry_delay <= 10.0:
        raise ValueError("LLM retry delay must be between 0 and 10 seconds.")
