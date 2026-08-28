"""Tests für die lokale Auswahl des Folgeaufnahme-Providers."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from voice.followup_factory import create_follow_up_capture


def make_settings(**changes):
    values = {
        "VOICE_FOLLOWUP_LOCAL": True,
        "VOICE_FOLLOWUP_PROVIDER": "vosk",
        "VOICE_FOLLOWUP_MIN_CONFIDENCE": 0.42,
        "VOSK_MODEL_PATH": r"F:\Vosk\models\vosk-model-small-de-0.15",
        "VOSK_AUDIO_DEVICE": "",
    }
    values.update(changes)
    return SimpleNamespace(**values)


class FollowUpFactoryTests(unittest.TestCase):
    @patch("voice.followup_factory.VoskFollowUpCapture")
    def test_vosk_is_default_local_provider(self, capture_type):
        capture = create_follow_up_capture(make_settings())

        capture_type.assert_called_once_with(
            r"F:\Vosk\models\vosk-model-small-de-0.15",
            min_confidence=0.42,
            audio_device=None,
        )
        capture_type.return_value.prepare.assert_called_once_with()
        self.assertIs(capture_type.return_value, capture)

    @patch("voice.followup_factory.WindowsSpeechFollowUpCapture")
    def test_windows_provider_remains_available_explicitly(self, capture_type):
        capture = create_follow_up_capture(
            make_settings(VOICE_FOLLOWUP_PROVIDER="windows"),
        )

        capture_type.assert_called_once_with(min_confidence=0.42)
        capture_type.return_value.prepare.assert_called_once_with()
        self.assertIs(capture_type.return_value, capture)

    @patch("voice.followup_factory.VoskFollowUpCapture")
    def test_local_follow_up_can_be_disabled(self, capture_type):
        capture = create_follow_up_capture(
            make_settings(VOICE_FOLLOWUP_LOCAL=False),
        )

        self.assertIsNone(capture)
        capture_type.assert_not_called()

    def test_unknown_provider_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "VOICE_FOLLOWUP_PROVIDER"):
            create_follow_up_capture(
                make_settings(VOICE_FOLLOWUP_PROVIDER="cloud"),
            )


if __name__ == "__main__":
    unittest.main()
