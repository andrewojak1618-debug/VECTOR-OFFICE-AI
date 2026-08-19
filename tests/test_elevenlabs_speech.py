"""Tests for optional cloud TTS and its mandatory local fallback."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx

from vector.elevenlabs_speech import (
    NATURAL_VECTOR_AUDIO_FILTER,
    ElevenLabsSpeech,
    ElevenLabsVoiceSettings,
)
from vector.speech import SpeechStyle, VectorSpeech
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
