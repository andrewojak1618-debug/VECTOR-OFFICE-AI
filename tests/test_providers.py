import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from brain.context import ChatMessage, ConversationContext
from brain.providers import (
    FallbackProvider,
    OllamaProvider,
    OpenAIProvider,
    ProviderNotice,
    create_language_model,
)
from brain.fallback_provider import (
    FallbackProvider as ExtractedFallbackProvider,
    ProviderNotice as ExtractedProviderNotice,
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
    def test_fallback_provider_keeps_compatible_import_path(self):
        self.assertIs(ExtractedFallbackProvider, FallbackProvider)
        self.assertIs(ExtractedProviderNotice, ProviderNotice)

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

    def test_openai_client_receives_explicit_timeout_and_retry_limit(self):
        with patch("brain.providers.OpenAI") as create_client:
            OpenAIProvider(
                "test-key",
                "test-model",
                timeout=45.0,
                max_attempts=3,
            )

        create_client.assert_called_once_with(
            api_key="test-key",
            timeout=45.0,
            max_retries=2,
        )

    def test_ollama_provider_maps_messages(self):
        def handle_request(request):
            payload = __import__("json").loads(request.content)
            self.assertEqual("test-model", payload["model"])
            self.assertFalse(payload["stream"])
            self.assertFalse(payload["think"])
            self.assertEqual("30m", payload["keep_alive"])
            self.assertEqual(64, payload["options"]["num_predict"])
            self.assertEqual(4096, payload["options"]["num_ctx"])
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

    def test_ollama_provider_can_request_deterministic_sampling(self):
        def handle_request(request):
            payload = __import__("json").loads(request.content)
            self.assertEqual(0.0, payload["options"]["temperature"])
            return httpx.Response(200, json={"message": {"content": "Okay"}})

        client = httpx.Client(
            base_url="http://test",
            transport=httpx.MockTransport(handle_request),
        )
        provider = OllamaProvider(
            "http://test",
            "test-model",
            temperature=0.0,
            client=client,
        )

        self.assertEqual("Okay", provider.generate(MESSAGES))

    def test_ollama_provider_rejects_invalid_temperature(self):
        with self.assertRaisesRegex(ValueError, "temperature"):
            OllamaProvider("http://test", "test-model", temperature=2.1)

    def test_ollama_provider_rejects_unbounded_generation_settings(self):
        with self.assertRaisesRegex(ValueError, "output limit"):
            OllamaProvider("http://test", "test-model", max_output_tokens=513)
        with self.assertRaisesRegex(ValueError, "context window"):
            OllamaProvider("http://test", "test-model", context_window=512)
        with self.assertRaisesRegex(ValueError, "keep-alive"):
            OllamaProvider("http://test", "test-model", keep_alive=" ")

    def test_openai_and_ollama_receive_identical_personality_rules(self):
        messages = ConversationContext().messages()
        openai_client = FakeOpenAIClient()
        captured = {}

        def handle_request(request):
            payload = __import__("json").loads(request.content)
            captured["messages"] = payload["messages"]
            return httpx.Response(200, json={"message": {"content": "Okay"}})

        ollama_client = httpx.Client(
            base_url="http://test",
            transport=httpx.MockTransport(handle_request),
        )
        OpenAIProvider("key", "model", openai_client).generate(messages)
        OllamaProvider("http://test", "model", client=ollama_client).generate(
            messages
        )

        openai_messages = openai_client.responses.request["input"]
        self.assertEqual(openai_messages, captured["messages"])
        self.assertIn("C1-Niveau", openai_messages[0]["content"])

    def test_factory_rejects_unknown_provider(self):
        settings = SimpleNamespace(LLM_PROVIDER="unknown")

        with self.assertRaises(ValueError):
            create_language_model(settings)

    def test_factory_applies_bounded_local_generation_settings(self):
        settings = SimpleNamespace(
            LLM_PROVIDER="ollama",
            OLLAMA_HOST="http://test",
            OLLAMA_MODEL="test-model",
            LLM_REQUEST_TIMEOUT=45.0,
            LLM_MAX_ATTEMPTS=1,
            LLM_RETRY_DELAY=0.0,
            OLLAMA_TEMPERATURE=0.1,
            OLLAMA_MAX_OUTPUT_TOKENS=72,
            OLLAMA_CONTEXT_WINDOW=2048,
        )

        provider = create_language_model(settings)

        self.assertEqual(0.1, provider.temperature)
        self.assertEqual(72, provider.max_output_tokens)
        self.assertEqual(2048, provider.context_window)

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

    def test_ollama_retries_one_transient_server_failure(self):
        attempts = 0
        delays = []

        def handle_request(request):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return httpx.Response(503, request=request)
            return httpx.Response(
                200,
                json={"message": {"content": "Wieder erreichbar"}},
            )

        client = httpx.Client(
            base_url="http://test",
            transport=httpx.MockTransport(handle_request),
        )
        provider = OllamaProvider(
            "http://test",
            "test-model",
            max_attempts=2,
            retry_delay=0.25,
            client=client,
            sleeper=delays.append,
        )

        self.assertEqual("Wieder erreichbar", provider.generate(MESSAGES))
        self.assertEqual(2, attempts)
        self.assertEqual([0.25], delays)

    def test_ollama_does_not_retry_permanent_client_error(self):
        attempts = 0

        def handle_request(request):
            nonlocal attempts
            attempts += 1
            return httpx.Response(400, request=request)

        client = httpx.Client(
            base_url="http://test",
            transport=httpx.MockTransport(handle_request),
        )
        provider = OllamaProvider(
            "http://test",
            "test-model",
            max_attempts=3,
            retry_delay=0,
            client=client,
        )

        with self.assertRaisesRegex(RuntimeError, "Ollama request failed"):
            provider.generate(MESSAGES)
        self.assertEqual(1, attempts)

    def test_provider_request_policy_is_bounded(self):
        with self.assertRaisesRegex(ValueError, "timeout"):
            OllamaProvider("http://test", "model", timeout=0.5)
        with self.assertRaisesRegex(ValueError, "attempts"):
            OllamaProvider("http://test", "model", max_attempts=6)
        with self.assertRaisesRegex(ValueError, "delay"):
            OllamaProvider("http://test", "model", retry_delay=-1)


if __name__ == "__main__":
    unittest.main()
