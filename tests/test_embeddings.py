import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from memory.embeddings import (
    EmbeddingError,
    EmbeddingModelUnavailableError,
    EmbeddingProvider,
    EmbeddingText,
    EmbeddingTimeoutError,
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

    def test_model_availability_reads_native_dimension(self):
        def handle_request(request):
            if request.url.path == "/api/show":
                payload = json.loads(request.content)
                self.assertEqual("embeddinggemma", payload["model"])
                self.assertNotIn("input", payload)
                return httpx.Response(
                    200,
                    json={"model_info": {"gemma3.embedding_length": 768}},
                )
            self.assertEqual("/api/tags", request.url.path)
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "embeddinggemma:latest",
                            "digest": "sha256-model-version",
                        }
                    ]
                },
            )

        provider = self._provider(handle_request)
        info = provider.ensure_model_available()

        self.assertEqual("embeddinggemma", info.model_name)
        self.assertEqual("sha256-model-version", info.model_version)
        self.assertEqual(768, info.dimension)
        self.assertEqual(768, provider.dimension)
        self.assertEqual("sha256-model-version", provider.model_version)

    def test_missing_model_is_reported_with_install_command(self):
        provider = self._provider(
            lambda request: httpx.Response(404, json={"error": "not found"})
        )

        with self.assertRaisesRegex(
            EmbeddingModelUnavailableError,
            "ollama pull embeddinggemma",
        ):
            provider.ensure_model_available()

    def test_batch_embeds_multiple_sections_in_one_request(self):
        request_count = 0

        def handle_request(request):
            nonlocal request_count
            request_count += 1
            payload = json.loads(request.content)
            self.assertEqual(["Abschnitt A", "Abschnitt B"], payload["input"])
            return httpx.Response(
                200,
                json={
                    "model": "embeddinggemma:latest",
                    "embeddings": [[0.1, 0.2], [0.3, 0.4]],
                },
            )

        provider = self._provider(handle_request)
        results = provider.embed_many(
            (EmbeddingText("Abschnitt A"), EmbeddingText("Abschnitt B"))
        )

        self.assertEqual(1, request_count)
        self.assertEqual(2, len(results))
        self.assertEqual("Abschnitt B", results[1].text.value)
        self.assertEqual(2, provider.dimension)

    def test_empty_batch_is_rejected_before_request(self):
        provider = self._provider(lambda request: self._response(request))

        with self.assertRaisesRegex(ValueError, "At least one"):
            provider.embed_many(())

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

    def test_embedding_timeout_is_reported_separately(self):
        def fail(request):
            raise httpx.ReadTimeout("private delay", request=request)

        provider = self._provider(fail)

        with self.assertRaisesRegex(EmbeddingTimeoutError, "timed out"):
            provider.embed(EmbeddingText("Test"))

    def test_invalid_response_is_rejected(self):
        provider = self._provider(
            lambda request: httpx.Response(200, json={"embeddings": []})
        )

        with self.assertRaisesRegex(EmbeddingError, "invalid embedding response"):
            provider.embed(EmbeddingText("Test"))

    def test_inconsistent_batch_dimensions_are_rejected(self):
        provider = self._provider(
            lambda request: httpx.Response(
                200,
                json={
                    "model": "embeddinggemma",
                    "embeddings": [[0.1, 0.2], [0.3]],
                },
            )
        )

        with self.assertRaisesRegex(EmbeddingError, "inconsistent"):
            provider.embed_many((EmbeddingText("A"), EmbeddingText("B")))

    def test_sensitive_text_is_never_printed_on_failure(self):
        sensitive_text = "Vertrauliches Dokumentgeheimnis 4711"
        provider = self._provider(
            lambda request: httpx.Response(200, json={"embeddings": []})
        )

        with patch("builtins.print") as print_mock:
            with self.assertRaises(EmbeddingError) as raised:
                provider.embed(EmbeddingText(sensitive_text))

        print_mock.assert_not_called()
        self.assertNotIn(sensitive_text, str(raised.exception))

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

    def test_timeout_outside_safe_range_is_rejected(self):
        for timeout in (0.9, 600.1):
            with self.subTest(timeout=timeout), self.assertRaisesRegex(
                ValueError,
                "between 1 and 600",
            ):
                OllamaEmbeddingProvider(
                    "http://127.0.0.1:11434",
                    "embeddinggemma",
                    timeout=timeout,
                )

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
