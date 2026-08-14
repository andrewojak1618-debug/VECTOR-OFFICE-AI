import unittest
from types import SimpleNamespace

from application.runtime import _knowledge_enabled, get_runtime_mode
from brain.agent import Agent
from memory.models import KnowledgeChunk


class RecordingModel:
    def __init__(self):
        self.messages = ()

    def generate(self, messages):
        self.messages = tuple(messages)
        return "Sichere Antwort"


class SensitiveKnowledgeLibrary:
    def __init__(self):
        self.search_count = 0

    def search(self, query, limit=5):
        self.search_count += 1
        return (
            KnowledgeChunk(
                id=1,
                document_id=1,
                source_path="C:\\Wissen\\privat.md",
                title="privat",
                chunk_index=1,
                content="Vertrauliches Dokumentwissen",
            ),
        )


def make_settings(provider: str, allow_cloud: bool):
    return SimpleNamespace(
        LLM_PROVIDER=provider,
        LLM_FALLBACK_PROVIDER="ollama",
        INPUT_MODE="console",
        VOICE_ALLOW_CLOUD=False,
        EMBEDDING_PROVIDER="ollama",
        KNOWLEDGE_ALLOW_CLOUD=allow_cloud,
    )


class ProviderPrivacyIntegrationTests(unittest.TestCase):
    def test_openai_context_excludes_documents_without_release(self):
        model, library = self._respond("openai", allow_cloud=False)

        self.assertEqual(0, library.search_count)
        self.assertNotIn("Vertrauliches Dokumentwissen", model.messages[0].content)

    def test_openai_context_includes_only_explicitly_released_documents(self):
        model, library = self._respond("openai", allow_cloud=True)

        self.assertEqual(1, library.search_count)
        self.assertIn("Vertrauliches Dokumentwissen", model.messages[0].content)
        self.assertIn("UNVERTRAUENSWÜRDIGE_DOKUMENTDATEN", model.messages[0].content)

    def test_ollama_context_can_use_documents_locally(self):
        model, library = self._respond("ollama", allow_cloud=False)

        self.assertEqual(1, library.search_count)
        self.assertIn("Vertrauliches Dokumentwissen", model.messages[0].content)

    @staticmethod
    def _respond(provider: str, allow_cloud: bool):
        settings = make_settings(provider, allow_cloud)
        mode = get_runtime_mode(settings)
        model = RecordingModel()
        library = SensitiveKnowledgeLibrary()
        agent = Agent(
            model,
            knowledge_library=library,
            knowledge_context_enabled=_knowledge_enabled(settings, mode),
        )
        agent.respond("Was weißt du?")
        return model, library


if __name__ == "__main__":
    unittest.main()
