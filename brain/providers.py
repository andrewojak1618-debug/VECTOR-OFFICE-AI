from typing import Any, Sequence

import httpx
from openai import OpenAI, OpenAIError

from brain.agent import LanguageModel
from brain.context import ChatMessage


class OpenAIProvider:
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

        if client is None:
            client = OpenAI(api_key=api_key)

        self.model = model
        self.client = client

    def generate(self, messages: Sequence[ChatMessage]) -> str:
        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": message.role,
                        "content": message.content,
                    }
                    for message in messages
                ],
            )
        except OpenAIError:
            raise RuntimeError(
                "OpenAI request failed. Check API key, model access, and billing."
            ) from None

        return response.output_text


class OllamaProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = 120.0,
        client: httpx.Client | None = None,
    ):
        if not base_url.strip():
            raise ValueError("OLLAMA_HOST must not be empty.")

        if not model.strip():
            raise ValueError("OLLAMA_MODEL must not be empty.")

        self.model = model
        self.client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
        )

    def generate(self, messages: Sequence[ChatMessage]) -> str:
        try:
            response = self.client.post(
                "/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": message.role,
                            "content": message.content,
                        }
                        for message in messages
                    ],
                    "stream": False,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError:
            raise RuntimeError(
                "Ollama request failed. Check service, host, and model."
            ) from None

        content = response.json().get("message", {}).get("content", "")

        if not isinstance(content, str):
            raise RuntimeError("Ollama returned an invalid response.")

        return content


class FallbackProvider:
    def __init__(
        self,
        primary: LanguageModel,
        fallback: LanguageModel,
    ):
        self.primary = primary
        self.fallback = fallback

    def generate(self, messages: Sequence[ChatMessage]) -> str:
        try:
            content = self.primary.generate(messages)

            if content.strip():
                return content
        except RuntimeError:
            pass

        print("OpenAI unavailable. Using local Ollama fallback.")

        try:
            return self.fallback.generate(messages)
        except RuntimeError:
            raise RuntimeError(
                "OpenAI and the local Ollama fallback both failed."
            ) from None


def create_language_model(settings) -> LanguageModel:
    provider = settings.LLM_PROVIDER.lower().strip()

    if provider == "openai":
        primary = OpenAIProvider(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_MODEL,
        )

        fallback_provider = settings.LLM_FALLBACK_PROVIDER.lower().strip()

        if fallback_provider == "none":
            return primary

        if fallback_provider == "ollama":
            return FallbackProvider(
                primary=primary,
                fallback=OllamaProvider(
                    base_url=settings.OLLAMA_HOST,
                    model=settings.OLLAMA_MODEL,
                ),
            )

        raise ValueError(
            "LLM_FALLBACK_PROVIDER must be either 'ollama' or 'none'."
        )

    if provider == "ollama":
        return OllamaProvider(
            base_url=settings.OLLAMA_HOST,
            model=settings.OLLAMA_MODEL,
        )

    raise ValueError(
        "LLM_PROVIDER must be either 'openai' or 'ollama'."
    )
