import unittest
from types import SimpleNamespace

from unittest.mock import MagicMock, patch

import application.runtime as runtime_module
from application.runtime import (
    _create_tool_registry,
    _create_follow_up_capture,
    _ensure_ollama,
    _knowledge_enabled,
    register_provider_statuses,
    _run_input_mode,
    _run_wirepod_input,
    get_runtime_mode,
    run_application,
)
from application.connection_supervisor import ConnectionSupervisor
from brain.ollama_runtime import OllamaRuntime
from vector.client import VectorClient


def make_settings(**overrides):
    values = {
        "LLM_PROVIDER": "openai",
        "LLM_FALLBACK_PROVIDER": "ollama",
        "INPUT_MODE": "console",
        "VOICE_ALLOW_CLOUD": False,
        "EMBEDDING_PROVIDER": "ollama",
        "KNOWLEDGE_ALLOW_CLOUD": False,
        "TTS_PROVIDER": "onecore",
        "TTS_ALLOW_CLOUD": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class RuntimeModeTests(unittest.TestCase):
    @patch("application.runtime._prepare_vector", return_value=None)
    @patch("application.runtime._emit_runtime_start")
    @patch("application.runtime._create_diagnostics")
    @patch("application.runtime._print_header")
    def test_blocked_vector_start_reports_failure_to_host(
        self,
        _print_header,
        create_diagnostics,
        _emit_runtime_start,
        _prepare_vector,
    ):
        create_diagnostics.return_value = MagicMock()

        self.assertIs(run_application(make_settings()), False)

    def test_runtime_keeps_wirepod_client_dependency_available(self):
        self.assertIs(VectorClient, runtime_module.VectorClient)

    def test_runtime_keeps_ollama_status_dependency_available(self):
        self.assertIs(OllamaRuntime, runtime_module.OllamaRuntime)

    def test_runtime_registers_only_controlled_production_tools(self):
        registry = _create_tool_registry(
            MagicMock(),
            wirepod_checker=lambda: True,
            ollama_checker=lambda: True,
            library_status_reader=lambda: (),
            memory_status_reader=lambda: None,
        )

        self.assertEqual(
            (
                "development.code_quality_status",
                "development.documentation_status",
                "development.latest_change",
                "development.latest_tool_status",
                "development.next_roadmap_item",
                "development.open_project_directory",
                "development.open_project_document",
                "development.project_document_catalog",
                "development.project_status",
                "development.run_core_tests",
                "development.summarize_project_document",
                "knowledge.library_status",
                "memory.local_status",
                "office.local_datetime",
                "research.python_latest_version",
                "research.python_source_status",
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

    def test_runtime_registers_all_central_provider_states(self):
        settings = make_settings(
            TTS_PROVIDER="elevenlabs",
            TTS_ALLOW_CLOUD=True,
        )
        connections = ConnectionSupervisor()

        register_provider_statuses(
            settings,
            get_runtime_mode(settings),
            connections,
        )

        self.assertEqual(
            {
                "elevenlabs": "unavailable",
                "ollama": "unavailable",
                "openai": "unavailable",
                "vector-sdk": "unavailable",
                "wirepod": "unavailable",
            },
            connections.provider_overview(),
        )

    def test_runtime_marks_unselected_optional_providers_disabled(self):
        settings = make_settings(
            LLM_PROVIDER="ollama",
            LLM_FALLBACK_PROVIDER="none",
        )
        connections = ConnectionSupervisor()

        register_provider_statuses(
            settings,
            get_runtime_mode(settings),
            connections,
        )

        overview = connections.provider_overview()
        self.assertEqual("disabled", overview["openai"])
        self.assertEqual("disabled", overview["elevenlabs"])

    @patch("application.runtime_startup.OllamaRuntime")
    def test_private_wirepod_voice_preloads_local_chat_model(self, runtime_type):
        settings = make_settings(
            INPUT_MODE="wirepod",
            OLLAMA_HOST="http://127.0.0.1:11434",
            OLLAMA_EXECUTABLE="",
            OLLAMA_MODEL="llama3.2:3b",
            OLLAMA_REQUEST_TIMEOUT=90.0,
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

    @patch("application.runtime_startup.OllamaRuntime")
    def test_private_voice_blocks_when_model_preload_fails(self, runtime_type):
        settings = make_settings(
            INPUT_MODE="wirepod",
            OLLAMA_HOST="http://127.0.0.1:11434",
            OLLAMA_EXECUTABLE="",
            OLLAMA_MODEL="llama3.2:3b",
            OLLAMA_REQUEST_TIMEOUT=90.0,
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

    @patch("application.runtime.run_voice_conversation")
    @patch("application.runtime.create_local_follow_up_capture")
    @patch("application.runtime.WirePodTranscriptListener")
    def test_wirepod_runtime_wires_bounded_follow_up_capture(
        self,
        listener_type,
        create_follow_up,
        run_voice,
    ):
        settings = make_settings(
            WIREPOD_HOST="http://127.0.0.1:8080",
            WIREPOD_REQUEST_TIMEOUT=4.0,
            VECTOR_SERIAL="0dd1fd3b",
            VOICE_LISTEN_TIMEOUT=120,
            VOICE_FOLLOWUP_TIMEOUT=5,
            VOICE_FOLLOWUP_LOCAL=True,
            VOICE_CONVERSATION_FOLLOWUP=True,
            VOICE_FOLLOWUP_MIN_CONFIDENCE=0.42,
        )
        agent = MagicMock()
        speech = MagicMock()
        connections = MagicMock()

        _run_wirepod_input(settings, agent, speech, connections)

        listener_type.assert_called_once_with(
            settings.WIREPOD_HOST,
            request_timeout=4.0,
        )
        create_follow_up.assert_called_once_with(settings)
        run_voice.assert_called_once_with(
            agent,
            speech,
            listener_type.return_value,
            listen_timeout=120,
            connections=connections,
            follow_up=create_follow_up.return_value,
            follow_up_timeout=5,
            conversation_follow_up=True,
        )

    @patch("application.runtime.create_local_follow_up_capture")
    def test_local_follow_up_delegates_to_provider_factory(self, create_follow_up):
        settings = make_settings(VOICE_FOLLOWUP_LOCAL=False)

        self.assertIs(create_follow_up.return_value, _create_follow_up_capture(settings))
        create_follow_up.assert_called_once_with(settings)


if __name__ == "__main__":
    unittest.main()
