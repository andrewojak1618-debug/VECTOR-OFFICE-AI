"""Tests for optional cloud TTS and its mandatory local fallback."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx

from diagnostics.events import StructuredDiagnosticReporter
from vector.elevenlabs_speech import (
    NATURAL_VECTOR_AUDIO_FILTER,
    ElevenLabsTimeoutError,
    ElevenLabsSpeech,
    ElevenLabsVoiceSettings,
)
from vector.speech import SpeechProviderNotice, SpeechStyle, VectorSpeech
from vector.speech_factory import create_speech_output


class FakeVectorClient:
    def play_wav(self, _path, volume=50):
        return bool(volume)


class RecordingHttpClient:
    def __init__(self, status_code=200, content=b"cloud-audio-data-more"):
        self.response = SimpleNamespace(status_code=status_code, content=content)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def cloud_settings(**overrides):
    values = {
        "TTS_VOICE": "Microsoft Stefan",
        "TTS_VOLUME": 90,
        "TTS_PROVIDER": "elevenlabs",
        "TTS_ALLOW_CLOUD": True,
        "ELEVENLABS_API_KEY": "secret-key",
        "ELEVENLABS_VOICE_ID": "felix-id",
        "ELEVENLABS_MODEL": "eleven_flash_v2_5",
        "ELEVENLABS_TIMEOUT": 15.0,
        "ELEVENLABS_STABILITY": 0.45,
        "ELEVENLABS_SIMILARITY": 0.75,
        "ELEVENLABS_STYLE": 0.0,
        "ELEVENLABS_SPEED": 1.02,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class ElevenLabsSpeechTests(unittest.TestCase):
    def setUp(self):
        self.local = VectorSpeech(FakeVectorClient(), volume=90)

    def test_request_uses_voice_id_secret_header_and_normalized_text(self):
        client = RecordingHttpClient()
        speech = ElevenLabsSpeech(
            self.local,
            "secret-key",
            "felix-id",
            client=client,
        )

        audio = speech._request_audio("Eine flüssige Antwort.")

        self.assertEqual(b"cloud-audio-data-more", audio)
        url, request = client.calls[0]
        self.assertTrue(url.endswith("/felix-id"))
        self.assertEqual("secret-key", request["headers"]["xi-api-key"])
        self.assertEqual("Eine flüssige Antwort.", request["json"]["text"])
        self.assertEqual("mp3_22050_32", request["params"]["output_format"])

    def test_failed_cloud_preparation_uses_local_voice(self):
        speech = ElevenLabsSpeech(
            self.local,
            "secret-key",
            "felix-id",
            client=RecordingHttpClient(),
        )
        fallback_audio = object()
        with patch.object(
            speech,
            "_request_audio",
            side_effect=RuntimeError("offline"),
        ), patch.object(
            self.local,
            "prepare",
            return_value=fallback_audio,
        ) as local_prepare:
            result = speech.prepare("Antwort", SpeechStyle.SUPPORTIVE)

        self.assertIs(fallback_audio, result)
        local_prepare.assert_called_once_with("Antwort", SpeechStyle.SUPPORTIVE)

    def test_cloud_fallback_and_recovery_notices_are_emitted_once(self):
        speech = ElevenLabsSpeech(self.local, "secret-key", "felix-id")
        local_audio = object()
        recovered_audio = object()
        stable_audio = object()
        outcomes = [
            RuntimeError("offline"),
            local_audio,
            recovered_audio,
            stable_audio,
        ]

        with patch.object(VectorSpeech, "prepare", side_effect=outcomes):
            self.assertIs(local_audio, speech.prepare("Antwort eins"))
            self.assertIs(
                SpeechProviderNotice.LOCAL_FALLBACK,
                speech.consume_notice(),
            )
            self.assertIsNone(speech.consume_notice())
            self.assertIs(recovered_audio, speech.prepare("Antwort zwei"))
            self.assertIs(
                SpeechProviderNotice.CLOUD_RECOVERED,
                speech.consume_notice(),
            )
            self.assertIsNone(speech.consume_notice())
            self.assertIs(stable_audio, speech.prepare("Antwort drei"))
            self.assertIsNone(speech.consume_notice())

    def test_cloud_lifecycle_diagnostics_never_include_speech_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "events.jsonl"
            diagnostics = StructuredDiagnosticReporter(path)
            speech = ElevenLabsSpeech(
                self.local,
                "secret-key",
                "felix-id",
                diagnostics=diagnostics,
            )
            outcomes = [RuntimeError("private failure"), object(), object()]
            with patch.object(VectorSpeech, "prepare", side_effect=outcomes):
                speech.prepare("private spoken answer")
                speech.prepare("another private answer")
            events = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(
            [
                "provider.started",
                "provider.error",
                "provider.fallback",
                "provider.started",
                "provider.finished",
                "provider.recovered",
            ],
            [event["code"] for event in events],
        )
        encoded = json.dumps(events)
        self.assertNotIn("private spoken answer", encoded)
        self.assertNotIn("secret-key", encoded)

    def test_continuous_cloud_outage_does_not_repeat_notice(self):
        speech = ElevenLabsSpeech(self.local, "secret-key", "felix-id")
        outcomes = [
            RuntimeError("offline one"),
            object(),
            RuntimeError("offline two"),
            object(),
        ]

        with patch.object(VectorSpeech, "prepare", side_effect=outcomes):
            speech.prepare("Antwort eins")
            first = speech.consume_notice()
            speech.prepare("Antwort zwei")
            second = speech.consume_notice()

        self.assertIs(SpeechProviderNotice.LOCAL_FALLBACK, first)
        self.assertIsNone(second)

    def test_thinking_prelude_always_remains_local(self):
        speech = ElevenLabsSpeech(self.local, "secret-key", "felix-id")
        with patch.object(
            self.local,
            "say_thinking_prelude",
            return_value=True,
        ) as local_prelude:
            self.assertTrue(speech.say_thinking_prelude())
        local_prelude.assert_called_once_with()

    def test_cloud_audio_preserves_more_dynamic_range(self):
        self.assertEqual(
            "loudnorm=I=-14:TP=-1:LRA=9",
            NATURAL_VECTOR_AUDIO_FILTER,
        )
        self.assertNotIn("acompressor", ElevenLabsSpeech.VECTOR_AUDIO_FILTER)

    def test_conversational_style_preserves_confirmed_voice_settings(self):
        speech = ElevenLabsSpeech(self.local, "secret-key", "felix-id")

        settings = speech._request_payload(
            "Antwort",
            SpeechStyle.CONVERSATIONAL,
        )["voice_settings"]

        self.assertEqual(0.45, settings["stability"])
        self.assertEqual(1.02, settings["speed"])
        self.assertEqual(0.0, settings["style"])

    def test_supportive_style_is_gentler_without_style_exaggeration(self):
        speech = ElevenLabsSpeech(self.local, "secret-key", "felix-id")

        settings = speech._request_payload(
            "Ich bin bei dir.",
            SpeechStyle.SUPPORTIVE,
        )["voice_settings"]

        self.assertAlmostEqual(0.37, settings["stability"])
        self.assertAlmostEqual(0.99, settings["speed"])
        self.assertEqual(0.0, settings["style"])

    def test_cautious_style_is_steadier_without_becoming_slow(self):
        speech = ElevenLabsSpeech(self.local, "secret-key", "felix-id")

        settings = speech._request_payload(
            "Dabei bin ich nicht ganz sicher.",
            SpeechStyle.CAUTIOUS,
        )["voice_settings"]

        self.assertAlmostEqual(0.52, settings["stability"])
        self.assertAlmostEqual(1.01, settings["speed"])
        self.assertEqual(0.0, settings["style"])

    def test_invalid_voice_controls_are_rejected(self):
        with self.assertRaises(ValueError):
            ElevenLabsVoiceSettings(stability=1.1)
        with self.assertRaises(ValueError):
            ElevenLabsVoiceSettings(speed=0.6)

    def test_http_failure_is_sanitized(self):
        client = MagicMock()
        client.post.side_effect = httpx.ConnectError("private transport detail")
        speech = ElevenLabsSpeech(
            self.local,
            "secret-key",
            "felix-id",
            client=client,
        )

        with self.assertRaisesRegex(RuntimeError, "could not be completed"):
            speech._request_audio("private answer")

    def test_timeout_is_reported_separately(self):
        client = MagicMock()
        request = httpx.Request("POST", "https://api.elevenlabs.io")
        client.post.side_effect = httpx.ReadTimeout("private delay", request=request)
        speech = ElevenLabsSpeech(
            self.local,
            "secret-key",
            "felix-id",
            client=client,
        )

        with self.assertRaisesRegex(ElevenLabsTimeoutError, "timed out"):
            speech._request_audio("private answer")

    def test_timeout_outside_safe_range_is_rejected(self):
        for timeout in (0.9, 60.1):
            with self.subTest(timeout=timeout), self.assertRaisesRegex(
                ValueError,
                "timeout",
            ):
                ElevenLabsSpeech(
                    self.local,
                    "secret-key",
                    "felix-id",
                    timeout=timeout,
                )


class SpeechFactoryTests(unittest.TestCase):
    def test_cloud_tts_requires_explicit_release(self):
        speech = create_speech_output(
            cloud_settings(TTS_ALLOW_CLOUD=False),
            FakeVectorClient(),
        )

        self.assertIs(type(speech), VectorSpeech)

    def test_missing_credentials_fall_back_to_onecore(self):
        speech = create_speech_output(
            cloud_settings(ELEVENLABS_API_KEY=""),
            FakeVectorClient(),
        )

        self.assertIs(type(speech), VectorSpeech)

    def test_complete_cloud_settings_create_elevenlabs_with_fallback(self):
        speech = create_speech_output(cloud_settings(), FakeVectorClient())

        self.assertIsInstance(speech, ElevenLabsSpeech)
        self.assertEqual("felix-id", speech.voice_id)
        self.assertEqual("Microsoft Stefan", speech.local_speech.voice)

    def test_unknown_tts_provider_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "TTS_PROVIDER"):
            create_speech_output(
                cloud_settings(TTS_PROVIDER="unknown"),
                FakeVectorClient(),
            )


if __name__ == "__main__":
    unittest.main()
