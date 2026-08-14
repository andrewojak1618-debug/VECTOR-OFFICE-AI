import json
import unittest
from types import SimpleNamespace

import httpx

from memory.embeddings import (
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingText,
    EmbeddingVector,
    OllamaEmbeddingProvider,
    create_embedding_provider,
)


class EmbeddingTypeTests(unittest.TestCase):
    def test_text_is_normalized(self):
        self.assertEqual("Hallo Vector", EmbeddingText("  Hallo Vector  ").value)

    def test_empty_text_is_rejected(self):
        with self.assertRaises(ValueError):
            EmbeddingText("   ")

    def test_vector_is_numeric_immutable_and_reports_dimension(self):
        vector = EmbeddingVector((1, 2.5, -3))

        self.assertEqual((1.0, 2.5, -3.0), vector.values)
        self.assertEqual(3, vector.dimension)

    def test_non_finite_vector_value_is_rejected(self):
        with self.assertRaises(ValueError):
            EmbeddingVector((1.0, float("nan")))


class OllamaEmbeddingProviderTests(unittest.TestCase):
    def test_provider_implements_neutral_protocol(self):
        provider = self._provider(lambda request: self._response(request))

        self.assertIsInstance(provider, EmbeddingProvider)

    def test_embed_maps_current_ollama_api_and_captures_metadata(self):
        def handle_request(request):
            payload = json.loads(request.content)
            self.assertEqual("/api/embed", request.url.path)
            self.assertEqual("embeddinggemma", payload["model"])
            self.assertEqual("Semantischer Test", payload["input"])
            self.assertFalse(payload["truncate"])
            self.assertEqual(3, payload["dimensions"])
            return self._response(request)

        provider = self._provider(handle_request, expected_dimension=3)
        result = provider.embed(EmbeddingText("Semantischer Test"))

        self.assertEqual("embeddinggemma:latest", result.model_name)
        self.assertEqual(3, result.dimension)
        self.assertEqual((0.1, 0.2, 0.3), result.vector.values)

    def test_dimension_is_inferred_when_not_configured(self):
        def handle_request(request):
            payload = json.loads(request.content)
            self.assertNotIn("dimensions", payload)
            return self._response(request)

        provider = self._provider(handle_request)

        self.assertEqual(3, provider.embed(EmbeddingText("Test")).dimension)

    def test_connection_failure_is_sanitized(self):
        def fail(request):
            raise httpx.ConnectError("sensitive local transport detail")

        provider = self._provider(fail)

        with self.assertRaisesRegex(EmbeddingError, "Local Ollama embedding failed"):
            provider.embed(EmbeddingText("Test"))

    def test_invalid_response_is_rejected(self):
        provider = self._provider(
            lambda request: httpx.Response(200, json={"embeddings": []})
        )

        with self.assertRaisesRegex(EmbeddingError, "invalid embedding response"):
            provider.embed(EmbeddingText("Test"))

    def test_unexpected_dimension_is_rejected(self):
        provider = self._provider(
            lambda request: self._response(request),
            expected_dimension=4,
        )

        with self.assertRaisesRegex(EmbeddingError, "unexpected embedding dimension"):
            provider.embed(EmbeddingText("Test"))

    def test_timeout_is_applied_to_default_http_client(self):
        provider = OllamaEmbeddingProvider(
            "http://127.0.0.1:11434",
            "embeddinggemma",
            timeout=12.5,
        )
        self.addCleanup(provider.client.close)

        self.assertEqual(12.5, provider.client.timeout.read)

    @staticmethod
    def _response(request):
        return httpx.Response(
            200,
            json={
                "model": "embeddinggemma:latest",
                "embeddings": [[0.1, 0.2, 0.3]],
            },
        )

    def _provider(self, handler, expected_dimension=None):
        client = httpx.Client(
            base_url="http://local-test",
            transport=httpx.MockTransport(handler),
        )
        self.addCleanup(client.close)
        return OllamaEmbeddingProvider(
            base_url="http://local-test",
            model_name="embeddinggemma",
            expected_dimension=expected_dimension,
            client=client,
        )


class EmbeddingFactoryTests(unittest.TestCase):
    def test_factory_rejects_cloud_embedding_provider(self):
        settings = SimpleNamespace(EMBEDDING_PROVIDER="openai")

        with self.assertRaisesRegex(ValueError, "local only"):
            create_embedding_provider(settings)

    def test_factory_builds_configured_local_provider(self):
        settings = SimpleNamespace(
            EMBEDDING_PROVIDER="ollama",
            OLLAMA_HOST="http://127.0.0.1:11434",
            OLLAMA_EMBEDDING_MODEL="embeddinggemma",
            OLLAMA_EMBEDDING_DIMENSION=768,
            OLLAMA_EMBEDDING_TIMEOUT=45,
        )

        provider = create_embedding_provider(settings)
        self.addCleanup(provider.client.close)

        self.assertEqual("embeddinggemma", provider.model_name)
        self.assertEqual(768, provider.expected_dimension)
        self.assertEqual(45, provider.timeout)


if __name__ == "__main__":
    unittest.main()
