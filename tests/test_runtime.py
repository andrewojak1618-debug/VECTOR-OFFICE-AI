import unittest
from types import SimpleNamespace

from unittest.mock import MagicMock, patch

from application.runtime import (
    _create_tool_registry,
    _ensure_ollama,
    _knowledge_enabled,
    _run_input_mode,
    get_runtime_mode,
)


def make_settings(**overrides):
    values = {
        "LLM_PROVIDER": "openai",
        "LLM_FALLBACK_PROVIDER": "ollama",
        "INPUT_MODE": "console",
        "VOICE_ALLOW_CLOUD": False,
        "EMBEDDING_PROVIDER": "ollama",
        "KNOWLEDGE_ALLOW_CLOUD": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class RuntimeModeTests(unittest.TestCase):
    def test_runtime_registers_only_controlled_production_tools(self):
        registry = _create_tool_registry(
            MagicMock(),
            wirepod_checker=lambda: True,
            ollama_checker=lambda: True,
            library_status_reader=lambda: (),
        )

        self.assertEqual(
            (
                "development.project_status",
                "development.run_core_tests",
                "knowledge.library_status",
                "office.local_datetime",
                "system.local_service_status",
                "vector.emergency_stop",
                "vector.list_actions",
                "vector.perform_action",
            ),
            tuple(item.name for item in registry.definitions()),
        )

    def test_runtime_requires_both_local_service_checks(self):
        with self.assertRaises(ValueError):
            _create_tool_registry(MagicMock(), wirepod_checker=lambda: True)

    def test_openai_console_uses_configured_ollama_fallback(self):
        mode = get_runtime_mode(make_settings())

        self.assertTrue(mode.needs_ollama)
        self.assertFalse(mode.local_voice_required)

    def test_private_wirepod_voice_requires_local_ollama(self):
        mode = get_runtime_mode(make_settings(INPUT_MODE="wirepod"))

        self.assertTrue(mode.needs_ollama)
        self.assertTrue(mode.local_voice_required)

    @patch("application.runtime.OllamaRuntime")
    def test_private_wirepod_voice_preloads_local_chat_model(self, runtime_type):
        settings = make_settings(
            INPUT_MODE="wirepod",
            OLLAMA_HOST="http://127.0.0.1:11434",
            OLLAMA_EXECUTABLE="",
            OLLAMA_MODEL="llama3.2:3b",
            LLM_REQUEST_TIMEOUT=90.0,
        )
        runtime = runtime_type.return_value
        runtime.ensure_available.return_value = True
        runtime.preload_model.return_value = True
        diagnostics = MagicMock()
        connections = MagicMock()

        self.assertTrue(
            _ensure_ollama(
                settings,
                get_runtime_mode(settings),
                diagnostics,
                connections,
            )
        )
        runtime.preload_model.assert_called_once_with("llama3.2:3b", 90.0)

    @patch("application.runtime.OllamaRuntime")
    def test_private_voice_blocks_when_model_preload_fails(self, runtime_type):
        settings = make_settings(
            INPUT_MODE="wirepod",
            OLLAMA_HOST="http://127.0.0.1:11434",
            OLLAMA_EXECUTABLE="",
            OLLAMA_MODEL="llama3.2:3b",
            LLM_REQUEST_TIMEOUT=90.0,
        )
        runtime = runtime_type.return_value
        runtime.ensure_available.return_value = True
        runtime.preload_model.return_value = False

        self.assertFalse(
            _ensure_ollama(
                settings,
                get_runtime_mode(settings),
                MagicMock(),
                MagicMock(),
            )
        )

    def test_unknown_provider_does_not_activate_fallback_implicitly(self):
        mode = get_runtime_mode(make_settings(
            LLM_PROVIDER="unknown",
            EMBEDDING_PROVIDER="unknown",
        ))

        self.assertFalse(mode.needs_ollama)

    def test_local_embeddings_require_ollama_without_llm_fallback(self):
        mode = get_runtime_mode(make_settings(LLM_FALLBACK_PROVIDER="none"))

        self.assertTrue(mode.needs_ollama)

    def test_openai_blocks_document_context_by_default(self):
        settings = make_settings()

        self.assertFalse(_knowledge_enabled(settings, get_runtime_mode(settings)))

    def test_openai_uses_documents_only_after_explicit_cloud_release(self):
        settings = make_settings(KNOWLEDGE_ALLOW_CLOUD=True)

        self.assertTrue(_knowledge_enabled(settings, get_runtime_mode(settings)))

    def test_ollama_can_use_local_documents_without_cloud_release(self):
        settings = make_settings(LLM_PROVIDER="ollama")

        self.assertTrue(_knowledge_enabled(settings, get_runtime_mode(settings)))

    def test_private_wirepod_mode_keeps_document_context_local(self):
        settings = make_settings(INPUT_MODE="wirepod")

        self.assertTrue(_knowledge_enabled(settings, get_runtime_mode(settings)))

    @patch("application.runtime._run_wirepod_input")
    def test_wirepod_mode_receives_shared_connection_supervisor(self, run_input):
        settings = make_settings(INPUT_MODE="wirepod")
        mode = get_runtime_mode(settings)
        agent = MagicMock()
        speech = MagicMock()
        diagnostics = MagicMock()
        connections = MagicMock()

        _run_input_mode(
            settings,
            mode,
            agent,
            speech,
            diagnostics,
            connections,
        )

        run_input.assert_called_once_with(settings, agent, speech, connections)


if __name__ == "__main__":
    unittest.main()
