"""Tests for the bounded conversational follow-up state."""

import unittest
from unittest.mock import MagicMock

from application.voice_followup import (
    FollowUpCaptureUnavailable,
    VoiceFollowUpWindow,
)


class RecordingCapture:
    def __init__(self, prepared=True, transcript="ja"):
        self.prepared = prepared
        self.transcript = transcript
        self.prepare_calls = 0
        self.capture_timeouts = []
        self.close_calls = 0

    def prepare(self):
        self.prepare_calls += 1
        return self.prepared

    def capture(self, timeout, free_text=False):
        self.capture_timeouts.append(timeout)
        self.free_text = free_text
        return self.transcript

    def close(self):
        self.close_calls += 1


class VoiceFollowUpWindowTests(unittest.TestCase):
    def test_active_window_uses_short_timeout_until_transcript(self):
        capture = RecordingCapture()
        window = VoiceFollowUpWindow(capture, timeout=5)

        self.assertTrue(window.update(awaiting_confirmation=True))
        listener = MagicMock()

        self.assertEqual("ja", window.listen(listener, 120))
        window.consume_transcript()
        listener.return_value = "normal"
        self.assertEqual("normal", window.listen(listener, 120))
        self.assertEqual(1, capture.prepare_calls)
        self.assertEqual([5], capture.capture_timeouts)
        listener.assert_called_once_with(120)

    def test_failed_activation_keeps_normal_timeout(self):
        window = VoiceFollowUpWindow(RecordingCapture(prepared=False), timeout=5)
        listener = MagicMock(return_value="normal")

        self.assertFalse(window.update(awaiting_confirmation=True))
        self.assertEqual("normal", window.listen(listener, 120))
        listener.assert_called_once_with(120)

    def test_conversational_window_uses_the_same_bounded_capture(self):
        capture = RecordingCapture(transcript="warum denkst du das")
        window = VoiceFollowUpWindow(capture, timeout=5)

        self.assertTrue(
            window.update(
                awaiting_confirmation=False,
                allow_conversation=True,
            )
        )
        self.assertTrue(window.is_conversational)

        self.assertEqual("warum denkst du das", window.listen(MagicMock(), 120))
        self.assertEqual([5], capture.capture_timeouts)
        self.assertTrue(capture.free_text)

    def test_confirmation_has_priority_over_conversation_window(self):
        window = VoiceFollowUpWindow(RecordingCapture(), timeout=5)

        window.update(
            awaiting_confirmation=True,
            allow_conversation=True,
        )

        self.assertTrue(window.is_confirmation)
        self.assertFalse(window.is_conversational)

    def test_natural_thanks_variants_end_only_the_content_window(self):
        window = VoiceFollowUpWindow(RecordingCapture(), timeout=5)
        for text in ("Danke.", "Vielen Dank", "Dankeschön", "Danke dir"):
            with self.subTest(text=text):
                window.update(False, allow_conversation=True)
                self.assertTrue(window.is_end_signal(text))

        window.update(True, allow_conversation=False)
        self.assertFalse(window.is_end_signal("Danke"))

    def test_capture_failure_falls_back_to_default_listener(self):
        capture = RecordingCapture()
        capture.capture = MagicMock(
            side_effect=FollowUpCaptureUnavailable("private detail"),
        )
        window = VoiceFollowUpWindow(capture, timeout=5)
        listener = MagicMock(return_value="ja")
        window.update(awaiting_confirmation=True)

        self.assertEqual("ja", window.listen(listener, 120))
        self.assertFalse(window.active)
        listener.assert_called_once_with(120)

    def test_timeout_is_reported_only_once(self):
        window = VoiceFollowUpWindow(RecordingCapture(), timeout=5)
        window.update(awaiting_confirmation=True)

        self.assertTrue(window.consume_timeout())
        self.assertFalse(window.consume_timeout())

    def test_close_releases_stateful_capture(self):
        capture = RecordingCapture()
        window = VoiceFollowUpWindow(capture, timeout=5)
        window.update(awaiting_confirmation=True)

        window.close()

        self.assertFalse(window.active)
        self.assertEqual(1, capture.close_calls)

    def test_timeout_is_bounded(self):
        for timeout in (0.9, 10.1):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                VoiceFollowUpWindow(None, timeout=timeout)


if __name__ == "__main__":
    unittest.main()
