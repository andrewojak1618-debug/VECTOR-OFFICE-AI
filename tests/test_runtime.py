import unittest
from types import SimpleNamespace

from application.runtime import get_runtime_mode


def make_settings(**overrides):
    values = {
        "LLM_PROVIDER": "openai",
        "LLM_FALLBACK_PROVIDER": "ollama",
        "INPUT_MODE": "console",
        "VOICE_ALLOW_CLOUD": False,
        "EMBEDDING_PROVIDER": "ollama",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class RuntimeModeTests(unittest.TestCase):
    def test_openai_console_uses_configured_ollama_fallback(self):
        mode = get_runtime_mode(make_settings())

        self.assertTrue(mode.needs_ollama)
        self.assertFalse(mode.local_voice_required)

    def test_private_wirepod_voice_requires_local_ollama(self):
        mode = get_runtime_mode(make_settings(INPUT_MODE="wirepod"))

        self.assertTrue(mode.needs_ollama)
        self.assertTrue(mode.local_voice_required)

    def test_unknown_provider_does_not_activate_fallback_implicitly(self):
        mode = get_runtime_mode(make_settings(
            LLM_PROVIDER="unknown",
            EMBEDDING_PROVIDER="unknown",
        ))

        self.assertFalse(mode.needs_ollama)

    def test_local_embeddings_require_ollama_without_llm_fallback(self):
        mode = get_runtime_mode(make_settings(LLM_FALLBACK_PROVIDER="none"))

        self.assertTrue(mode.needs_ollama)


if __name__ == "__main__":
    unittest.main()
