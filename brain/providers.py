"""Language-model adapters and bounded provider resilience."""

import time
from collections.abc import Callable, Sequence
from typing import Any

import httpx
from openai import OpenAI, OpenAIError

from brain.agent import LanguageModel
from brain.context import ChatMessage
from brain.fallback_provider import FallbackProvider, ProviderNotice
from brain.provider_diagnostics import emit_provider
from diagnostics.events import DiagnosticLevel, StructuredDiagnosticReporter


DEFAULT_OLLAMA_TEMPERATURE = 0.25
DEFAULT_OLLAMA_MAX_OUTPUT_TOKENS = 64
DEFAULT_OLLAMA_CONTEXT_WINDOW = 4_096
DEFAULT_OLLAMA_KEEP_ALIVE = "30m"


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
        diagnostics: StructuredDiagnosticReporter | None = None,
    ):
        if not api_key.strip():
            raise ValueError("OPENAI_API_KEY is required for the OpenAI provider.")
        if not model.strip():
            raise ValueError("OPENAI_MODEL must not be empty.")
        _validate_request_policy(timeout, max_attempts, 0.0)
        self.model = model
        self.diagnostics = diagnostics
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
            emit_provider(
                self.diagnostics,
                DiagnosticLevel.ERROR,
                "openai",
                "request.failed",
                reason_code="provider-error",
            )
            raise RuntimeError(
                "OpenAI request failed. Check API key, model access, and billing."
            ) from None
        emit_provider(
            self.diagnostics,
            DiagnosticLevel.INFO,
            "openai",
            "request.completed",
            status="success",
        )
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
        temperature: float = DEFAULT_OLLAMA_TEMPERATURE,
        max_output_tokens: int = DEFAULT_OLLAMA_MAX_OUTPUT_TOKENS,
        context_window: int = DEFAULT_OLLAMA_CONTEXT_WINDOW,
        keep_alive: str = DEFAULT_OLLAMA_KEEP_ALIVE,
        client: httpx.Client | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        diagnostics: StructuredDiagnosticReporter | None = None,
    ):
        if not base_url.strip():
            raise ValueError("OLLAMA_HOST must not be empty.")
        if not model.strip():
            raise ValueError("OLLAMA_MODEL must not be empty.")
        generation = (temperature, max_output_tokens, context_window, keep_alive)
        _validate_ollama_generation_policy(*generation)
        _validate_request_policy(timeout, max_attempts, retry_delay)
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.context_window = context_window
        self.keep_alive = keep_alive.strip()
        self.max_attempts = max_attempts
        self.retry_delay = retry_delay
        self.sleeper = sleeper
        self.diagnostics = diagnostics
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
                response = self._send(messages)
            except httpx.HTTPError as exc:
                if not self._may_retry(exc, attempt):
                    break
                self._report_retry(attempt)
                self.sleeper(self.retry_delay)
                continue
            self._report_success(attempt)
            return response
        emit_provider(
            self.diagnostics,
            DiagnosticLevel.ERROR,
            "ollama",
            "request.failed",
            max_attempts=self.max_attempts,
            reason_code="provider-error",
        )
        raise RuntimeError(
            "Ollama request failed. Check service, host, and model."
        ) from None

    def _send(self, messages: Sequence[ChatMessage]) -> httpx.Response:
        response = self.client.post(
            "/api/chat",
            json=self._request_payload(messages),
        )
        response.raise_for_status()
        return response

    def _report_retry(self, attempt: int) -> None:
        emit_provider(
            self.diagnostics,
            DiagnosticLevel.WARNING,
            "ollama",
            "request.retrying",
            attempt=attempt,
            max_attempts=self.max_attempts,
            reason_code="transient-provider-error",
        )

    def _report_success(self, attempt: int) -> None:
        emit_provider(
            self.diagnostics,
            DiagnosticLevel.INFO,
            "ollama",
            "request.completed",
            attempt=attempt,
            max_attempts=self.max_attempts,
            status="success",
        )

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
            "think": False,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_output_tokens,
                "num_ctx": self.context_window,
            },
        }
        return payload

    @staticmethod
    def _response_content(response: httpx.Response) -> str:
        content = response.json().get("message", {}).get("content", "")
        if not isinstance(content, str):
            raise RuntimeError("Ollama returned an invalid response.")
        return content


def create_language_model(
    settings,
    diagnostics: StructuredDiagnosticReporter | None = None,
) -> LanguageModel:
    """Build the configured language model and optional local fallback."""
    provider = settings.LLM_PROVIDER.casefold().strip()
    if provider == "openai":
        return _create_openai_model(settings, diagnostics)
    if provider == "ollama":
        return _create_ollama_model(settings, diagnostics)
    raise ValueError("LLM_PROVIDER must be either 'openai' or 'ollama'.")


def _create_openai_model(settings, diagnostics=None) -> LanguageModel:
    primary = OpenAIProvider(
        settings.OPENAI_API_KEY,
        settings.OPENAI_MODEL,
        timeout=_request_timeout(settings),
        max_attempts=_max_attempts(settings),
        diagnostics=diagnostics,
    )
    fallback = settings.LLM_FALLBACK_PROVIDER.casefold().strip()
    if fallback == "none":
        return primary
    if fallback == "ollama":
        return FallbackProvider(
            primary,
            _create_ollama_model(settings, diagnostics),
            diagnostics,
        )
    raise ValueError("LLM_FALLBACK_PROVIDER must be either 'ollama' or 'none'.")


def _create_ollama_model(settings, diagnostics=None) -> OllamaProvider:
    return OllamaProvider(
        settings.OLLAMA_HOST,
        settings.OLLAMA_MODEL,
        timeout=_request_timeout(settings),
        max_attempts=_max_attempts(settings),
        retry_delay=getattr(settings, "LLM_RETRY_DELAY", 0.5),
        temperature=getattr(
            settings,
            "OLLAMA_TEMPERATURE",
            DEFAULT_OLLAMA_TEMPERATURE,
        ),
        max_output_tokens=getattr(
            settings,
            "OLLAMA_MAX_OUTPUT_TOKENS",
            DEFAULT_OLLAMA_MAX_OUTPUT_TOKENS,
        ),
        context_window=getattr(
            settings,
            "OLLAMA_CONTEXT_WINDOW",
            DEFAULT_OLLAMA_CONTEXT_WINDOW,
        ),
        diagnostics=diagnostics,
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


def _validate_ollama_generation_policy(
    temperature: float,
    max_output_tokens: int,
    context_window: int,
    keep_alive: str,
) -> None:
    if not 0.0 <= temperature <= 2.0:
        raise ValueError("Ollama temperature must be between 0 and 2.")
    if type(max_output_tokens) is not int or not 16 <= max_output_tokens <= 512:
        raise ValueError("Ollama output limit must be between 16 and 512.")
    if type(context_window) is not int or not 1_024 <= context_window <= 32_768:
        raise ValueError("Ollama context window must be between 1024 and 32768.")
    if not keep_alive.strip():
        raise ValueError("Ollama keep-alive must not be empty.")
