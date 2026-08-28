import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from vector.speech import REFLECTIVE_PRELUDES, SpeechStyle, VectorSpeech
from vector.speech_prosody import normalize_speech_text


class FakeVectorClient:
    def __init__(self):
        self.calls = []

    def play_wav(self, path, volume=50):
        self.calls.append((Path(path), volume))
        return True


class VectorSpeechTests(unittest.TestCase):
    def test_model_formatting_is_normalized_for_continuous_speech(self):
        text = "## Antwort\n- Das ist **wichtig** — und verständlich."

        self.assertEqual(
            "Antwort Das ist wichtig, und verständlich.",
            normalize_speech_text(text),
        )

    def test_dash_normalization_never_leaves_space_before_comma(self):
        text = "Wach und aufmerksam – wie ein heller Morgen."

        normalized = normalize_speech_text(text)

        self.assertEqual("Wach und aufmerksam, wie ein heller Morgen.", normalized)
        self.assertNotIn(" ,", normalized)

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
        self.assertEqual(
            SpeechStyle.CONVERSATIONAL,
            synthesize.call_args.args[2],
        )
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
        with patch("vector.speech.secrets.choice") as choose:
            content = VectorSpeech._speech_content(
                "Freiheit & Verantwortung. Eine mögliche Sichtweise?",
                SpeechStyle.REFLECTIVE,
            )

        self.assertIn('<prosody rate="+7%"', content)
        self.assertIn('pitch="-1%"', content)
        self.assertNotIn('<break time="180ms"/>', content)
        self.assertIn('<break time="150ms"/>', content)
        self.assertIn("Freiheit &amp;", content)
        self.assertIn("Verantwortung.", content)
        self.assertEqual(1, content.count("<prosody"))
        choose.assert_not_called()

    def test_each_reflective_prelude_can_be_selected_independently(self):
        self.assertEqual(
            ("IPA-Summton", "Ich schätze", "Lass mich überlegen"),
            tuple(prelude.label for prelude in REFLECTIVE_PRELUDES),
        )
        speech = VectorSpeech(FakeVectorClient())
        for prelude in REFLECTIVE_PRELUDES:
            with self.subTest(prelude=prelude.label), patch(
                "vector.speech.secrets.choice",
                return_value=prelude,
            ) as choose, patch.object(
                speech,
                "_prepare_ssml_and_play",
                return_value=True,
            ) as play:
                self.assertTrue(speech.say_thinking_prelude())
                self.assertIn(prelude.markup, play.call_args.args[0])
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
            with self.subTest(prelude=prelude.label):
                content = VectorSpeech._thinking_content(prelude)
                self.assertIn(
                    f'{prelude.markup}<break time="{expected_breaks[prelude.label]}ms"/>',
                    content,
                )

    def test_neutral_style_uses_faster_bounded_sentence_prosody(self):
        text = "Guten Tag & willkommen."

        with patch("vector.speech.secrets.choice") as choose:
            content = VectorSpeech._speech_content(text, SpeechStyle.NEUTRAL)

        self.assertIn('<prosody rate="+8%" pitch="+0%">', content)
        self.assertIn("Guten Tag &amp; willkommen.", content)
        self.assertEqual(1, content.count("<prosody"))
        choose.assert_not_called()

    def test_conversational_style_adds_warm_bounded_sentence_melody(self):
        text = "Freiheit entsteht, wenn wir bewusst entscheiden. Das zählt."

        content = VectorSpeech._speech_content(
            text,
            SpeechStyle.CONVERSATIONAL,
        )

        self.assertIn('<prosody rate="+10%" pitch="+0%">', content)
        self.assertNotIn('<break time="85ms"/>', content)
        self.assertIn('<break time="90ms"/>', content)
        self.assertEqual(1, content.count("<prosody"))

    def test_supportive_style_stays_fluid_with_gentler_emphasis(self):
        content = VectorSpeech._speech_content(
            "Das klingt schwer, wir schauen gemeinsam hin. Du bist nicht allein.",
            SpeechStyle.SUPPORTIVE,
        )

        self.assertIn('<prosody rate="+8%" pitch="-2%">', content)
        self.assertNotIn('<break time="100ms"/>', content)
        self.assertIn('<break time="120ms"/>', content)
        self.assertEqual(1, content.count("<prosody"))

    def test_cautious_style_marks_limits_without_becoming_slow(self):
        content = VectorSpeech._speech_content(
            "Das ist unsicher, prüfe zuerst die Verbindung. Warte kurz.",
            SpeechStyle.CAUTIOUS,
        )

        self.assertIn('<prosody rate="+9%" pitch="-1%">', content)
        self.assertNotIn('<break time="120ms"/>', content)
        self.assertIn('<break time="140ms"/>', content)
        self.assertEqual(1, content.count("<prosody"))

    def test_short_sentence_stays_in_one_fluid_prosody_block(self):
        content = VectorSpeech._speech_content("Guten Morgen.", SpeechStyle.NEUTRAL)

        self.assertIn(">Guten Morgen.</prosody>", content)
        self.assertEqual(1, content.count("<prosody"))

    def test_invalid_speech_style_is_rejected(self):
        speech = VectorSpeech(FakeVectorClient())

        with self.assertRaises(TypeError):
            speech.say("Guten Tag", "reflective")

    def test_prepared_audio_exists_until_playback_and_is_then_removed(self):
        client = FakeVectorClient()
        speech = VectorSpeech(client)

        with patch.object(speech, "_synthesize_german_wav"), patch.object(
            speech,
            "_convert_for_vector",
            side_effect=lambda _source, output: self._write_wav(
                output,
                VectorSpeech.SAMPLE_RATE,
            ),
        ):
            prepared = speech.prepare("Eine vorbereitete Antwort.")

        self.assertTrue(prepared.path.is_file())
        self.assertTrue(speech.play_prepared(prepared))
        self.assertFalse(prepared.path.exists())

    def test_prepare_rejects_invalid_input_before_tts(self):
        speech = VectorSpeech(FakeVectorClient())

        with self.assertRaises(ValueError):
            speech.prepare("  ")
        with self.assertRaises(TypeError):
            speech.prepare("Antwort", "supportive")

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
