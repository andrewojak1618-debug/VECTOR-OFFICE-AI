import unittest
from types import SimpleNamespace

import httpx

from brain.context import ChatMessage
from brain.providers import (
    FallbackProvider,
    OllamaProvider,
    OpenAIProvider,
    create_language_model,
)


MESSAGES = (
    ChatMessage(role="system", content="Antworte auf Deutsch."),
    ChatMessage(role="user", content="Hallo"),
)


class FakeResponses:
    def __init__(self):
        self.request = None

    def create(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(output_text="Guten Tag!")


class FakeOpenAIClient:
    def __init__(self):
        self.responses = FakeResponses()


class ProviderTests(unittest.TestCase):
    def test_fallback_provider_uses_primary_when_available(self):
        primary = SimpleNamespace(generate=lambda messages: "Cloud-Antwort")
        fallback = SimpleNamespace(generate=lambda messages: "Lokal-Antwort")

        provider = FallbackProvider(primary, fallback)

        self.assertEqual("Cloud-Antwort", provider.generate(MESSAGES))

    def test_fallback_provider_uses_ollama_after_primary_failure(self):
        def fail(messages):
            raise RuntimeError("OpenAI unavailable")

        primary = SimpleNamespace(generate=fail)
        fallback = SimpleNamespace(generate=lambda messages: "Lokal-Antwort")

        provider = FallbackProvider(primary, fallback)

        self.assertEqual("Lokal-Antwort", provider.generate(MESSAGES))

    def test_openai_provider_maps_messages(self):
        client = FakeOpenAIClient()
        provider = OpenAIProvider(
            api_key="test-key",
            model="test-model",
            client=client,
        )

        result = provider.generate(MESSAGES)

        self.assertEqual("Guten Tag!", result)
        self.assertEqual("test-model", client.responses.request["model"])
        self.assertEqual(
            "Hallo",
            client.responses.request["input"][1]["content"],
        )

    def test_ollama_provider_maps_messages(self):
        def handle_request(request):
            payload = __import__("json").loads(request.content)
            self.assertEqual("test-model", payload["model"])
            self.assertFalse(payload["stream"])
            self.assertEqual("Hallo", payload["messages"][1]["content"])
            return httpx.Response(
                200,
                json={"message": {"content": "Guten Tag!"}},
            )

        client = httpx.Client(
            base_url="http://test",
            transport=httpx.MockTransport(handle_request),
        )
        provider = OllamaProvider(
            base_url="http://test",
            model="test-model",
            client=client,
        )

        self.assertEqual("Guten Tag!", provider.generate(MESSAGES))

    def test_factory_rejects_unknown_provider(self):
        settings = SimpleNamespace(LLM_PROVIDER="unknown")

        with self.assertRaises(ValueError):
            create_language_model(settings)

    def test_ollama_provider_sanitizes_connection_errors(self):
        def handle_request(request):
            raise httpx.ConnectError("sensitive transport details")

        client = httpx.Client(
            base_url="http://test",
            transport=httpx.MockTransport(handle_request),
        )
        provider = OllamaProvider(
            base_url="http://test",
            model="test-model",
            client=client,
        )

        with self.assertRaisesRegex(RuntimeError, "Ollama request failed"):
            provider.generate(MESSAGES)


if __name__ == "__main__":
    unittest.main()
