"""Tests für den lokalen Vosk-Folgeaufnahmeweg."""

import json
import tempfile
import unittest
from pathlib import Path

from application.voice_followup import FollowUpCaptureUnavailable
from voice.vosk_followup import VoskFollowUpCapture


class FakeModel:
    def __init__(self, path):
        self.path = path


class FakeRecognizer:
    payload = {
        "text": "danke",
        "result": [{"word": "danke", "conf": 0.91}],
    }
    instances = []

    def __init__(self, model, sample_rate, grammar=None):
        self.model = model
        self.sample_rate = sample_rate
        self.grammar = grammar
        self.words_enabled = False
        self.__class__.instances.append(self)

    def SetWords(self, enabled):
        self.words_enabled = enabled

    def AcceptWaveform(self, data):
        return bool(data)

    def Result(self):
        return json.dumps(self.payload)

    def FinalResult(self):
        return self.Result()


class FakeStream:
    def __init__(self, callback):
        self.callback = callback

    def __enter__(self):
        self.callback(b"audio", 1, None, None)
        return self

    def __exit__(self, *_args):
        return False


class FakeSoundDevice:
    def __init__(self):
        self.stream_options = None

    def query_devices(self, _device=None, kind=None):
        if kind != "input":
            raise AssertionError("Only the input device may be queried.")
        return {"default_samplerate": 16_000, "max_input_channels": 1}

    def RawInputStream(self, **options):
        self.stream_options = options
        return FakeStream(options["callback"])


def create_model_tree(root: Path) -> Path:
    model = root / "model"
    for relative in ("am/final.mdl", "conf/mfcc.conf", "graph/HCLr.fst"):
        target = model / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"model")
    return model


class VoskFollowUpCaptureTests(unittest.TestCase):
    def setUp(self):
        FakeRecognizer.instances.clear()
        FakeRecognizer.payload = {
            "text": "danke",
            "result": [{"word": "danke", "conf": 0.91}],
        }

    def test_prepare_rejects_missing_model_without_loading_dependencies(self):
        loaded = []
        capture = VoskFollowUpCapture(
            "missing-model",
            dependency_loader=lambda: loaded.append(True),
        )

        self.assertFalse(capture.prepare())
        self.assertEqual([], loaded)

    def test_conversation_capture_uses_local_microphone_and_returns_text(self):
        with tempfile.TemporaryDirectory() as directory:
            audio = FakeSoundDevice()
            capture = VoskFollowUpCapture(
                create_model_tree(Path(directory)),
                min_confidence=0.5,
                dependency_loader=lambda: (FakeModel, FakeRecognizer, audio),
            )

            self.assertTrue(capture.prepare())
            self.assertEqual("danke", capture.capture(1, free_text=True))

        recognizer = FakeRecognizer.instances[-1]
        self.assertIsNone(recognizer.grammar)
        self.assertTrue(recognizer.words_enabled)
        self.assertEqual(1, audio.stream_options["channels"])
        self.assertEqual("int16", audio.stream_options["dtype"])

    def test_confirmation_capture_uses_restricted_grammar(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = VoskFollowUpCapture(
                create_model_tree(Path(directory)),
                dependency_loader=lambda: (
                    FakeModel,
                    FakeRecognizer,
                    FakeSoundDevice(),
                ),
            )

            self.assertEqual("danke", capture.capture(1, free_text=False))

        grammar = json.loads(FakeRecognizer.instances[-1].grammar)
        self.assertIn("ja", grammar)
        self.assertIn("nein", grammar)
        self.assertNotIn("warum denkst du das", grammar)

    def test_low_confidence_result_is_not_forwarded(self):
        FakeRecognizer.payload = {
            "text": "danke",
            "result": [{"word": "danke", "conf": 0.2}],
        }
        with tempfile.TemporaryDirectory() as directory:
            capture = VoskFollowUpCapture(
                create_model_tree(Path(directory)),
                min_confidence=0.5,
                dependency_loader=lambda: (
                    FakeModel,
                    FakeRecognizer,
                    FakeSoundDevice(),
                ),
            )

            self.assertIsNone(capture.capture(1, free_text=True))

    def test_audio_failure_uses_content_free_unavailable_error(self):
        class BrokenSoundDevice(FakeSoundDevice):
            def RawInputStream(self, **_options):
                raise RuntimeError("private device details")

        with tempfile.TemporaryDirectory() as directory:
            capture = VoskFollowUpCapture(
                create_model_tree(Path(directory)),
                dependency_loader=lambda: (
                    FakeModel,
                    FakeRecognizer,
                    BrokenSoundDevice(),
                ),
            )

            with self.assertRaisesRegex(
                FollowUpCaptureUnavailable,
                "Local follow-up capture is unavailable",
            ):
                capture.capture(1, free_text=True)


if __name__ == "__main__":
    unittest.main()
