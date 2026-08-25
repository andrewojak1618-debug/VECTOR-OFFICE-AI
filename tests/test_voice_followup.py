"""Tests for the bounded conversational follow-up state."""

import unittest

from application.voice_followup import VoiceFollowUpWindow


class RecordingCapture:
    def __init__(self, result=True):
        self.result = result
        self.calls = 0

    def activate(self):
        self.calls += 1
        return self.result


class VoiceFollowUpWindowTests(unittest.TestCase):
    def test_active_window_uses_short_timeout_until_transcript(self):
        capture = RecordingCapture()
        window = VoiceFollowUpWindow(capture, timeout=5)

        self.assertTrue(window.update(awaiting_confirmation=True))
        self.assertEqual(5, window.listening_timeout(120))
        window.consume_transcript()
        self.assertEqual(120, window.listening_timeout(120))
        self.assertEqual(1, capture.calls)

    def test_failed_activation_keeps_normal_timeout(self):
        window = VoiceFollowUpWindow(RecordingCapture(result=False), timeout=5)

        self.assertFalse(window.update(awaiting_confirmation=True))
        self.assertEqual(120, window.listening_timeout(120))

    def test_timeout_is_reported_only_once(self):
        window = VoiceFollowUpWindow(RecordingCapture(), timeout=5)
        window.update(awaiting_confirmation=True)

        self.assertTrue(window.consume_timeout())
        self.assertFalse(window.consume_timeout())

    def test_timeout_is_bounded(self):
        for timeout in (0.9, 10.1):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                VoiceFollowUpWindow(None, timeout=timeout)


if __name__ == "__main__":
    unittest.main()
