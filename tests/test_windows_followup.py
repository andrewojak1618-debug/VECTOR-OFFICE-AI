"""Tests for the firmware-free local Windows follow-up capture."""

import base64
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from application.voice_followup import FollowUpCaptureUnavailable
from voice.windows_followup import WindowsSpeechFollowUpCapture


class WindowsSpeechFollowUpCaptureTests(unittest.TestCase):
    def test_prepare_detects_and_caches_german_recognizer(self):
        runner = MagicMock(return_value=_result("available\n"))
        capture = WindowsSpeechFollowUpCapture(runner=runner)

        self.assertTrue(capture.prepare())
        self.assertTrue(capture.prepare())
        self.assertEqual(1, runner.call_count)

    def test_capture_returns_bounded_recognized_text(self):
        runner = MagicMock(return_value=_result("Ja, den Ordner bitte.\n"))
        capture = WindowsSpeechFollowUpCapture(runner=runner)

        self.assertEqual("Ja, den Ordner bitte.", capture.capture(5))
        command = runner.call_args.args[0]
        self.assertIn("-EncodedCommand", command)
        self.assertIn("de-DE", _decode_script(command))
        self.assertEqual(8.0, runner.call_args.kwargs["timeout"])

    def test_empty_recognition_returns_none(self):
        capture = WindowsSpeechFollowUpCapture(runner=MagicMock(return_value=_result()))

        self.assertIsNone(capture.capture(5))

    def test_process_error_raises_only_safe_capture_error(self):
        runner = MagicMock(return_value=_result("", returncode=7))
        capture = WindowsSpeechFollowUpCapture(runner=runner)

        with self.assertRaisesRegex(
            FollowUpCaptureUnavailable,
            "Local follow-up capture is unavailable",
        ):
            capture.capture(5)

    def test_process_timeout_raises_safe_capture_error(self):
        runner = MagicMock(side_effect=subprocess.TimeoutExpired("secret", 8))
        capture = WindowsSpeechFollowUpCapture(runner=runner)

        with self.assertRaises(FollowUpCaptureUnavailable) as raised:
            capture.capture(5)

        self.assertNotIn("secret", str(raised.exception))

    def test_runner_hides_window_and_never_uses_shell(self):
        runner = MagicMock(return_value=_result("ja"))
        capture = WindowsSpeechFollowUpCapture(runner=runner)

        capture.capture(5)

        kwargs = runner.call_args.kwargs
        self.assertNotIn("shell", kwargs)
        self.assertEqual(
            getattr(subprocess, "CREATE_NO_WINDOW", 0),
            kwargs["creationflags"],
        )

    def test_timeout_confidence_and_culture_are_restricted(self):
        with self.assertRaises(ValueError):
            WindowsSpeechFollowUpCapture(min_confidence=1.1)
        capture = WindowsSpeechFollowUpCapture()
        with self.assertRaises(ValueError):
            capture.capture(11)
        with self.assertRaises(ValueError):
            WindowsSpeechFollowUpCapture(culture="en-US").prepare()


def _result(stdout="", returncode=0):
    return SimpleNamespace(stdout=stdout, returncode=returncode)


def _decode_script(command):
    encoded = command[command.index("-EncodedCommand") + 1]
    return base64.b64decode(encoded).decode("utf-16-le")


if __name__ == "__main__":
    unittest.main()
