"""Language-model adapters and bounded provider resilience."""

import time
from collections.abc import Callable, Sequence
from typing import Any

import httpx
from openai import APITimeoutError, OpenAI, OpenAIError

from brain.agent import LanguageModel
from brain.context import ChatMessage
from brain.fallback_provider import FallbackProvider, ProviderNotice
from brain.provider_diagnostics import ProviderErrorCode, ProviderOperation
from diagnostics.events import StructuredDiagnosticReporter


DEFAULT_OLLAMA_TEMPERATURE = 0.25
DEFAULT_OLLAMA_MAX_OUTPUT_TOKENS = 64
DEFAULT_OLLAMA_CONTEXT_WINDOW = 4_096
DEFAULT_OLLAMA_KEEP_ALIVE = "30m"


class ProviderTimeoutError(RuntimeError):
    """Meldet eine Anbieterfrist ohne Anfrageinhalte oder geheime Werte."""


def _message_payload(messages: Sequence[ChatMessage]) -> list[dict[str, str]]:
    """Überführt normalisierte Nachrichten in das gemeinsame Anbieterformat."""
    return [
        {"role": message.role, "content": message.content}
        for message in messages
    ]


class OpenAIProvider:
    """Generate responses through the OpenAI Responses API."""

    response_source = "openai"

    def __init__(
        self,
        api_key: str,
        model: str,
        client: Any | None = None,
        timeout: float = 120.0,
        max_attempts: int = 2,
        diagnostics: StructuredDiagnosticReporter | None = None,
    ):
        """Initialisiert den OpenAI-Client mit validierten Anfragegrenzen."""
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
        """Liefert eine Modellantwort, ohne Anbieterfehler offenzulegen."""
        operation = ProviderOperation(self.diagnostics, "openai")
        try:
            response = self.client.responses.create(
                model=self.model,
                input=_message_payload(messages),
            )
        except APITimeoutError:
            operation.timeout()
            raise ProviderTimeoutError(
                "OpenAI request timed out. The local fallback may be used."
            ) from None
        except OpenAIError:
            operation.error(ProviderErrorCode.PROVIDER_UNAVAILABLE)
            raise RuntimeError(
                "OpenAI request failed. Check API key, model access, and billing."
            ) from None
        operation.finished()
        return response.output_text

class OllamaProvider:
    """Generate responses through a local Ollama chat endpoint."""

    response_source = "ollama"

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
        """Initialisiert den lokalen Ollama-Adapter mit begrenzten Erzeugungswerten."""
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
        self.max_attempts, self.retry_delay = max_attempts, retry_delay
        self.sleeper = sleeper
        self.diagnostics = diagnostics
        self.client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
        )

    def generate(self, messages: Sequence[ChatMessage]) -> str:
        """Liefert eine lokale Antwort und bereinigt Transportfehler."""
        operation = ProviderOperation(self.diagnostics, "ollama")
        try:
            response = self._request(messages)
            content = self._response_content(response)
        except ProviderTimeoutError:
            operation.timeout()
            raise
        except RuntimeError:
            operation.error(ProviderErrorCode.PROVIDER_UNAVAILABLE)
            raise
        except (KeyError, ValueError):
            operation.error(ProviderErrorCode.INVALID_RESPONSE)
            raise RuntimeError("Ollama returned an invalid response.") from None
        operation.finished()
        return content

    def _request(self, messages: Sequence[ChatMessage]) -> httpx.Response:
        """Sendet eine Ollama-Anfrage mit begrenzten Wiederholungen."""
        last_error: httpx.HTTPError | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self._send(messages)
            except httpx.HTTPError as exc:
                last_error = exc
                if not self._may_retry(exc, attempt):
                    break
                self.sleeper(self.retry_delay)
                continue
            return response
        timed_out = isinstance(last_error, httpx.TimeoutException)
        if timed_out:
            raise ProviderTimeoutError(
                "Ollama request timed out. Check the local service and model."
            ) from None
        raise RuntimeError(
            "Ollama request failed. Check service, host, and model."
        ) from None

    def _send(self, messages: Sequence[ChatMessage]) -> httpx.Response:
        """Sendet genau eine lokale Chatanfrage mit festem Nutzdatenformat."""
        response = self.client.post(
            "/api/chat",
            json=self._request_payload(messages),
        )
        response.raise_for_status()
        return response

    def _may_retry(self, error: httpx.HTTPError, attempt: int) -> bool:
        """Erlaubt Wiederholungen nur für vorübergehende Transport- und Statusfehler."""
        if attempt >= self.max_attempts:
            return False
        if isinstance(error, httpx.RequestError):
            return True
        if isinstance(error, httpx.HTTPStatusError):
            status = error.response.status_code
            return status in {408, 409, 429} or status >= 500
        return False

    def _request_payload(self, messages: Sequence[ChatMessage]) -> dict:
        """Erzeugt die begrenzte lokale Ollama-Anfrage ohne Denkmodus."""
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
        """Entnimmt ausschließlich gültigen Text aus der lokalen Modellantwort."""
        content = response.json().get("message", {}).get("content", "")
        if not isinstance(content, str):
            raise RuntimeError("Ollama returned an invalid response.")
        return content


def create_language_model(
    settings,
    diagnostics: StructuredDiagnosticReporter | None = None,
) -> LanguageModel:
    """Erzeugt das konfigurierte Sprachmodell samt optionalem lokalem Rückfall."""
    provider = settings.LLM_PROVIDER.casefold().strip()
    if provider == "openai":
        return _create_openai_model(settings, diagnostics)
    if provider == "ollama":
        return _create_ollama_model(settings, diagnostics)
    raise ValueError("LLM_PROVIDER must be either 'openai' or 'ollama'.")


def _create_openai_model(settings, diagnostics=None) -> LanguageModel:
    """Erzeugt OpenAI und verbindet bei Freigabe den lokalen Ollama-Rückfall."""
    primary = OpenAIProvider(
        settings.OPENAI_API_KEY,
        settings.OPENAI_MODEL,
        timeout=_openai_timeout(settings),
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
    """Erzeugt den lokalen Ollama-Adapter aus begrenzten Einstellungen."""
    return OllamaProvider(
        settings.OLLAMA_HOST,
        settings.OLLAMA_MODEL,
        timeout=_ollama_timeout(settings),
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


def _openai_timeout(settings) -> float:
    """Liest ausschließlich die begrenzte OpenAI-Anfragefrist."""
    return getattr(settings, "OPENAI_REQUEST_TIMEOUT", 120.0)


def _ollama_timeout(settings) -> float:
    """Liest ausschließlich die begrenzte Ollama-Anfragefrist."""
    return getattr(settings, "OLLAMA_REQUEST_TIMEOUT", 120.0)


def _max_attempts(settings) -> int:
    """Liest die begrenzte Zahl der Modellversuche mit sicherem Standardwert."""
    return getattr(settings, "LLM_MAX_ATTEMPTS", 2)


def _validate_request_policy(
    timeout: float,
    max_attempts: int,
    retry_delay: float,
) -> None:
    """Validiert Frist, Versuchsanzahl und Wiederholungsverzögerung."""
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
    """Validiert lokale Temperatur-, Ausgabe-, Kontext- und Haltezeitgrenzen."""
    if not 0.0 <= temperature <= 2.0:
        raise ValueError("Ollama temperature must be between 0 and 2.")
    if type(max_output_tokens) is not int or not 16 <= max_output_tokens <= 512:
        raise ValueError("Ollama output limit must be between 16 and 512.")
    if type(context_window) is not int or not 1_024 <= context_window <= 32_768:
        raise ValueError("Ollama context window must be between 1024 and 32768.")
    if not keep_alive.strip():
        raise ValueError("Ollama keep-alive must not be empty.")
