"""Tests for the warmed firmware-free Windows follow-up capture."""

import base64
import io
import subprocess
import unittest
from unittest.mock import MagicMock

from application.voice_followup import FollowUpCaptureUnavailable
from voice.windows_followup import WindowsSpeechFollowUpCapture


class FakeProcess:
    """Stellt ein begrenztes zeilenbasiertes Unterprozessprotokoll bereit."""

    def __init__(self, responses):
        """Initialisiert feste Antworten und beschreibbare Standardeingabe."""
        self.stdin = io.StringIO()
        self.stdout = io.StringIO("".join(f"{item}\n" for item in responses))
        self.terminated = False

    def poll(self):
        """Meldet den Testprozess bis zur Beendigung als aktiv."""
        return 0 if self.terminated else None

    def wait(self, timeout):
        """Beendet den Testprozess innerhalb der festen Testfrist."""
        self.terminated = True
        return 0

    def terminate(self):
        """Markiert den Testprozess als zwangsweise beendet."""
        self.terminated = True


class WindowsSpeechFollowUpCaptureTests(unittest.TestCase):
    def test_prepare_starts_and_reuses_warmed_german_recognizer(self):
        process = FakeProcess(("READY",))
        factory = MagicMock(return_value=process)
        capture = WindowsSpeechFollowUpCapture(process_factory=factory)

        self.assertTrue(capture.prepare())
        self.assertTrue(capture.prepare())
        self.assertEqual(1, factory.call_count)
        capture.close()

    def test_capture_returns_bounded_recognized_text(self):
        encoded = base64.b64encode("Ja, bitte öffnen.".encode()).decode()
        process = FakeProcess(("READY", "LISTENING", f"RESULT:{encoded}"))
        capture = WindowsSpeechFollowUpCapture(
            process_factory=MagicMock(return_value=process),
        )

        self.assertEqual("Ja, bitte öffnen.", capture.capture(5))
        self.assertIn("CAPTURE CONFIRMATION 5000\n", process.stdin.getvalue())
        capture.close()

    def test_free_text_capture_selects_conversation_grammar(self):
        encoded = base64.b64encode("Warum ist das so?".encode()).decode()
        process = FakeProcess(("READY", "LISTENING", f"RESULT:{encoded}"))
        capture = WindowsSpeechFollowUpCapture(
            process_factory=MagicMock(return_value=process),
        )

        self.assertEqual("Warum ist das so?", capture.capture(5, free_text=True))
        self.assertIn("CAPTURE CONVERSATION 5000\n", process.stdin.getvalue())
        capture.close()

    def test_empty_recognition_returns_none(self):
        process = FakeProcess(("READY", "LISTENING", "RESULT:"))
        capture = WindowsSpeechFollowUpCapture(
            process_factory=MagicMock(return_value=process),
        )

        self.assertIsNone(capture.capture(5))
        capture.close()

    def test_missing_result_raises_only_safe_capture_error(self):
        process = FakeProcess(("READY", "LISTENING", "ERROR"))
        capture = WindowsSpeechFollowUpCapture(
            process_factory=MagicMock(return_value=process),
        )

        with self.assertRaisesRegex(
            FollowUpCaptureUnavailable,
            "Local follow-up capture is unavailable",
        ):
            capture.capture(5)

    def test_process_start_error_keeps_capture_unavailable(self):
        factory = MagicMock(side_effect=OSError("private device detail"))
        capture = WindowsSpeechFollowUpCapture(process_factory=factory)

        self.assertFalse(capture.prepare())
        with self.assertRaises(FollowUpCaptureUnavailable) as raised:
            capture.capture(5)

        self.assertNotIn("private", str(raised.exception))

    def test_process_hides_window_and_never_uses_shell(self):
        process = FakeProcess(("READY",))
        factory = MagicMock(return_value=process)
        capture = WindowsSpeechFollowUpCapture(process_factory=factory)

        self.assertTrue(capture.prepare())

        kwargs = factory.call_args.kwargs
        self.assertNotIn("shell", kwargs)
        self.assertEqual(
            getattr(subprocess, "CREATE_NO_WINDOW", 0),
            kwargs["creationflags"],
        )
        command = factory.call_args.args[0]
        self.assertIn("-EncodedCommand", command)
        script = _decode_script(command)
        self.assertIn("de-DE", script)
        self.assertIn("ja bitte öffnen", script)
        self.assertIn("DictationGrammar", script)
        self.assertIn("conversationControlGrammar", script)
        self.assertIn("vielen dank", script)
        capture.close()

    def test_close_releases_the_warmed_process(self):
        process = FakeProcess(("READY",))
        capture = WindowsSpeechFollowUpCapture(
            process_factory=MagicMock(return_value=process),
        )
        self.assertTrue(capture.prepare())

        capture.close()

        self.assertTrue(process.terminated)
        self.assertIn("STOP\n", process.stdin.getvalue())

    def test_timeout_confidence_and_culture_are_restricted(self):
        with self.assertRaises(ValueError):
            WindowsSpeechFollowUpCapture(min_confidence=1.1)
        capture = WindowsSpeechFollowUpCapture()
        with self.assertRaises(ValueError):
            capture.capture(11)
        with self.assertRaises(TypeError):
            capture.capture(5, free_text="yes")
        with self.assertRaises(ValueError):
            WindowsSpeechFollowUpCapture(culture="en-US").prepare()


def _decode_script(command):
    """Dekodiert das feste Testskript aus seinem PowerShell-Argument."""
    encoded = command[command.index("-EncodedCommand") + 1]
    return base64.b64decode(encoded).decode("utf-16-le")


if __name__ == "__main__":
    unittest.main()
