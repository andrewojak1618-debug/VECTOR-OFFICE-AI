"""Language-model adapters and bounded provider resilience."""

import time
from collections.abc import Callable, Sequence
from enum import Enum
from typing import Any

import httpx
from openai import OpenAI, OpenAIError

from brain.agent import LanguageModel
from brain.context import ChatMessage
from diagnostics.events import DiagnosticLevel, StructuredDiagnosticReporter


def _message_payload(messages: Sequence[ChatMessage]) -> list[dict[str, str]]:
    return [
        {"role": message.role, "content": message.content}
        for message in messages
    ]


class ProviderNotice(Enum):
    """Describe one consumable provider transition without response content."""

    LOCAL_FALLBACK = "local_fallback"
    ALL_UNAVAILABLE = "all_unavailable"


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
            _emit_provider(
                self.diagnostics,
                DiagnosticLevel.ERROR,
                "openai",
                "request.failed",
                reason_code="provider-error",
            )
            raise RuntimeError(
                "OpenAI request failed. Check API key, model access, and billing."
            ) from None
        _emit_provider(
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
        temperature: float | None = None,
        client: httpx.Client | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        diagnostics: StructuredDiagnosticReporter | None = None,
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
        _emit_provider(
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
        _emit_provider(
            self.diagnostics,
            DiagnosticLevel.WARNING,
            "ollama",
            "request.retrying",
            attempt=attempt,
            max_attempts=self.max_attempts,
            reason_code="transient-provider-error",
        )

    def _report_success(self, attempt: int) -> None:
        _emit_provider(
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

    def __init__(
        self,
        primary: LanguageModel,
        fallback: LanguageModel,
        diagnostics: StructuredDiagnosticReporter | None = None,
    ):
        self.primary = primary
        self.fallback = fallback
        self.diagnostics = diagnostics
        self._primary_unavailable = False
        self._pending_notice: ProviderNotice | None = None

    def generate(self, messages: Sequence[ChatMessage]) -> str:
        """Return the primary response or deliberately use the fallback."""
        content = self._try_primary(messages)
        if content:
            return content
        print("OpenAI unavailable. Using local Ollama fallback.")
        _emit_provider(
            self.diagnostics,
            DiagnosticLevel.WARNING,
            "provider",
            "fallback.activated",
            provider="openai",
            fallback="ollama",
            reason_code="primary-unavailable",
        )
        return self._generate_fallback(messages)

    def _try_primary(self, messages: Sequence[ChatMessage]) -> str:
        try:
            content = self.primary.generate(messages).strip()
        except RuntimeError:
            self._mark_primary_unavailable()
            return ""
        if not content:
            self._mark_primary_unavailable()
            return ""
        self._primary_unavailable = False
        self._pending_notice = None
        return content

    def _generate_fallback(self, messages: Sequence[ChatMessage]) -> str:
        try:
            content = self.fallback.generate(messages)
        except RuntimeError:
            if self._pending_notice is not None:
                self._pending_notice = ProviderNotice.ALL_UNAVAILABLE
            raise RuntimeError(
                "OpenAI and the local Ollama fallback both failed."
            ) from None
        if self._pending_notice is not None:
            self._pending_notice = ProviderNotice.LOCAL_FALLBACK
        return content

    def consume_notice(self) -> ProviderNotice | None:
        """Return one outage transition once and clear its pending state."""
        notice = self._pending_notice
        self._pending_notice = None
        return notice

    def _mark_primary_unavailable(self) -> None:
        if not self._primary_unavailable:
            self._pending_notice = ProviderNotice.ALL_UNAVAILABLE
        self._primary_unavailable = True


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


def _emit_provider(diagnostics, level, component, code, **details) -> None:
    if diagnostics is not None:
        diagnostics.emit(level, component, code, **details)
