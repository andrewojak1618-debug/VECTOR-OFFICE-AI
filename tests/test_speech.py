import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from vector.speech import VectorSpeech


class FakeVectorClient:
    def __init__(self):
        self.calls = []

    def play_wav(self, path, volume=50):
        self.calls.append((Path(path), volume))
        return True


class VectorSpeechTests(unittest.TestCase):
    def test_say_rejects_empty_text(self):
        speech = VectorSpeech(FakeVectorClient())

        self.assertFalse(speech.say("   "))

    def test_say_prepares_and_plays_audio(self):
        client = FakeVectorClient()
        speech = VectorSpeech(client, volume=90)

        with patch.object(speech, "_synthesize_german_wav") as synthesize, patch.object(
            speech, "_convert_for_vector"
        ) as convert, patch.object(speech, "_validate_vector_wav") as validate:
            self.assertTrue(speech.say("Guten Tag"))

        synthesize.assert_called_once()
        convert.assert_called_once()
        validate.assert_called_once()
        self.assertEqual(90, client.calls[0][1])

    def test_say_returns_false_when_synthesis_fails(self):
        speech = VectorSpeech(FakeVectorClient())

        with patch.object(
            speech,
            "_synthesize_german_wav",
            side_effect=RuntimeError("test failure"),
        ):
            self.assertFalse(speech.say("Guten Tag"))

    def test_validate_accepts_vector_audio_format(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "valid.wav"
            self._write_wav(path, sample_rate=VectorSpeech.SAMPLE_RATE)

            VectorSpeech._validate_vector_wav(path)

    def test_validate_rejects_wrong_sample_rate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "invalid.wav"
            self._write_wav(path, sample_rate=44100)

            with self.assertRaises(RuntimeError):
                VectorSpeech._validate_vector_wav(path)

    @staticmethod
    def _write_wav(path: Path, sample_rate: int) -> None:
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(VectorSpeech.CHANNELS)
            wav_file.setsampwidth(VectorSpeech.SAMPLE_WIDTH)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b"\x00\x00" * 16)


if __name__ == "__main__":
    unittest.main()
