"""Tests for the safe, repeatable central provider status command."""

import threading
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from diagnostics.provider_status import (
    VECTOR_PROBE_TIMEOUT_SECONDS,
    collect_provider_statuses,
    main,
    run_diagnostic,
)


def make_settings(**overrides):
    values = {
        "LLM_PROVIDER": "openai",
        "LLM_FALLBACK_PROVIDER": "ollama",
        "INPUT_MODE": "console",
        "VOICE_ALLOW_CLOUD": False,
        "EMBEDDING_PROVIDER": "ollama",
        "TTS_PROVIDER": "elevenlabs",
        "TTS_ALLOW_CLOUD": True,
        "OPENAI_API_KEY": "top-secret-openai",
        "OPENAI_MODEL": "configured-model",
        "ELEVENLABS_API_KEY": "top-secret-elevenlabs",
        "ELEVENLABS_VOICE_ID": "private-voice-id",
        "ELEVENLABS_MODEL": "configured-voice-model",
        "VECTOR_SERIAL": "private-vector-serial",
        "WIREPOD_HOST": "http://private-wirepod",
        "OLLAMA_HOST": "http://private-ollama",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def available_checkers(**overrides):
    checkers = {
        "vector-sdk": lambda: True,
        "wirepod": lambda: True,
        "ollama": lambda: True,
    }
    checkers.update({
        name.replace("_", "-"): value
        for name, value in overrides.items()
    })
    return checkers


class ProviderStatusTests(unittest.TestCase):
    @patch("diagnostics.provider_status.OllamaRuntime")
    @patch("diagnostics.provider_status.VectorClient")
    @patch("diagnostics.provider_status.VectorSDKClient")
    def test_default_vector_probe_uses_bounded_cold_start_timeout(
        self,
        vector_type,
        wirepod_type,
        ollama_type,
    ):
        vector_type.return_value.is_available.return_value = True
        wirepod_type.return_value.is_available.return_value = True
        ollama_type.return_value.is_available.return_value = True

        collect_provider_statuses(make_settings())

        vector_type.return_value.is_available.assert_called_once_with(
            timeout=VECTOR_PROBE_TIMEOUT_SECONDS,
        )

    def test_status_reports_local_health_and_configuration_only_cloud_state(self):
        output = []

        available = run_diagnostic(
            make_settings(),
            available_checkers(),
            writer=output.append,
        )

        text = "\n".join(output)
        self.assertTrue(available)
        self.assertIn("Vector SDK: healthy - erreichbar", text)
        self.assertIn("WirePod: healthy - erreichbar", text)
        self.assertIn("Ollama: healthy - erreichbar", text)
        self.assertIn("OpenAI: degraded - lokal konfiguriert", text)
        self.assertIn("ElevenLabs: degraded - lokal konfiguriert", text)

    def test_status_never_outputs_secret_or_endpoint_values(self):
        settings = make_settings()
        output = []

        run_diagnostic(settings, available_checkers(), writer=output.append)

        text = "\n".join(output)
        for private_value in (
            settings.OPENAI_API_KEY,
            settings.ELEVENLABS_API_KEY,
            settings.ELEVENLABS_VOICE_ID,
            settings.VECTOR_SERIAL,
            settings.WIREPOD_HOST,
            settings.OLLAMA_HOST,
        ):
            self.assertNotIn(private_value, text)

    def test_unselected_cloud_providers_are_disabled_without_checker_call(self):
        forbidden = MagicMock(side_effect=AssertionError("must not run"))
        settings = make_settings(
            LLM_PROVIDER="ollama",
            LLM_FALLBACK_PROVIDER="none",
            TTS_PROVIDER="onecore",
            TTS_ALLOW_CLOUD=False,
        )
        checkers = available_checkers(openai=forbidden, elevenlabs=forbidden)

        results = collect_provider_statuses(settings, checkers)

        states = {item.provider: item.health.value for item in results}
        self.assertEqual("disabled", states["openai"])
        self.assertEqual("disabled", states["elevenlabs"])
        forbidden.assert_not_called()

    def test_missing_enabled_cloud_configuration_is_unavailable(self):
        output = []
        settings = make_settings(
            OPENAI_API_KEY="",
            ELEVENLABS_VOICE_ID="",
        )

        available = run_diagnostic(
            settings,
            available_checkers(),
            writer=output.append,
        )

        text = "\n".join(output)
        self.assertFalse(available)
        self.assertEqual(2, text.count("lokale Konfiguration unvollständig"))

    def test_local_failure_and_exception_are_safely_reported(self):
        output = []

        def failing_check():
            raise RuntimeError("private transport detail")

        available = run_diagnostic(
            make_settings(),
            available_checkers(wirepod=lambda: False, ollama=failing_check),
            writer=output.append,
        )

        text = "\n".join(output)
        self.assertFalse(available)
        self.assertIn("WirePod: unavailable - nicht erreichbar", text)
        self.assertIn("Ollama: unavailable - Prüfung sicher fehlgeschlagen", text)
        self.assertNotIn("private transport detail", text)

    def test_local_check_stops_waiting_at_outer_timeout(self):
        blocker = threading.Event()
        results = collect_provider_statuses(
            make_settings(),
            available_checkers(vector_sdk=lambda: blocker.wait(0.3)),
            timeout=0.1,
        )

        vector = next(item for item in results if item.provider == "vector-sdk")
        self.assertEqual("unavailable", vector.health.value)
        self.assertEqual("Zeitlimit überschritten", vector.detail)

    def test_invalid_timeout_is_rejected_before_any_check(self):
        with self.assertRaisesRegex(ValueError, "timeout"):
            collect_provider_statuses(make_settings(), available_checkers(), timeout=0)

    @patch("diagnostics.provider_status.run_diagnostic", return_value=True)
    def test_module_main_maps_success_to_zero(self, run):
        self.assertEqual(0, main())
        run.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
