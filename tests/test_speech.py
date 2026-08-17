import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from vector.speech import REFLECTIVE_PRELUDES, SpeechStyle, VectorSpeech


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
        self.assertEqual(SpeechStyle.NEUTRAL, synthesize.call_args.args[2])
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

    def test_reflective_style_builds_bounded_ssml_with_safe_text(self):
        estimate = REFLECTIVE_PRELUDES[1]
        with patch("vector.speech.secrets.choice", return_value=estimate):
            content = VectorSpeech._speech_content(
                "Freiheit & Verantwortung. Eine mögliche Sichtweise?",
                SpeechStyle.REFLECTIVE,
            )

        self.assertIn('<prosody rate="-5%">', content)
        self.assertNotIn("pitch=", content)
        self.assertIn('<break time="180ms"/>', content)
        self.assertIn('Ich schätze<break time="320ms"/>', content)
        self.assertIn('<break time="190ms"/>', content)
        self.assertIn("Freiheit &amp; Verantwortung.", content)

    def test_each_reflective_prelude_can_be_selected_independently(self):
        self.assertEqual(
            ("IPA-Summton", "Ich schätze", "Lass mich überlegen"),
            tuple(prelude.label for prelude in REFLECTIVE_PRELUDES),
        )
        for prelude in REFLECTIVE_PRELUDES:
            with self.subTest(prelude=prelude.label), patch(
                "vector.speech.secrets.choice",
                return_value=prelude,
            ) as choose:
                content = VectorSpeech._speech_content(
                    "Freiheit braucht Verantwortung.",
                    SpeechStyle.REFLECTIVE,
                )
                self.assertIn(prelude.markup, content)
                choose.assert_called_once_with(REFLECTIVE_PRELUDES)

    def test_ipa_hum_uses_the_physically_selected_longer_rate(self):
        hum = REFLECTIVE_PRELUDES[0]

        self.assertIn('<prosody rate="-32%">', hum.markup)
        self.assertIn('<phoneme alphabet="ipa" ph="mː">', hum.markup)
        self.assertEqual(1500, hum.break_ms)

    def test_each_prelude_uses_its_configured_pause(self):
        expected_breaks = {
            "IPA-Summton": 1500,
            "Ich schätze": 320,
            "Lass mich überlegen": 2000,
        }

        for prelude in REFLECTIVE_PRELUDES:
            with self.subTest(prelude=prelude.label), patch(
                "vector.speech.secrets.choice",
                return_value=prelude,
            ):
                content = VectorSpeech._speech_content(
                    "Eine kurze Antwort.",
                    SpeechStyle.REFLECTIVE,
                )
                self.assertIn(
                    f'{prelude.markup}<break time="{expected_breaks[prelude.label]}ms"/>',
                    content,
                )

    def test_neutral_style_preserves_plain_text(self):
        text = "Guten Tag & willkommen."

        with patch("vector.speech.secrets.choice") as choose:
            self.assertEqual(
                text,
                VectorSpeech._speech_content(text, SpeechStyle.NEUTRAL),
            )
        choose.assert_not_called()

    def test_invalid_speech_style_is_rejected(self):
        speech = VectorSpeech(FakeVectorClient())

        with self.assertRaises(TypeError):
            speech.say("Guten Tag", "reflective")

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
