"""Spoken local notices for cloud and complete provider outages."""

import threading
import unittest
from unittest.mock import patch

from application.response_delivery import (
    CLOUD_OFFLINE_NOTICE,
    PROVIDER_OFFLINE_NOTICE,
    PROVIDER_RECOVERY_NOTICE,
    TTS_OFFLINE_NOTICE,
    VECTOR_UNAVAILABLE_MESSAGE,
    respond_and_speak,
)
from brain.agent import Agent
from brain.providers import FallbackProvider
from brain.response_quality import SAFE_PROVIDER_REPLACEMENT
from vector.speech import SpeechProviderNotice, SpeechStyle


class ScriptedProvider:
    def __init__(self, *outcomes):
        self.outcomes = iter(outcomes)

    def generate(self, _messages):
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class RecordingSpeech:
    def __init__(self):
        self.messages = []
        self.styles = []

    def say(self, text, style=SpeechStyle.CONVERSATIONAL):
        self.messages.append(text)
        self.styles.append(style)
        return True


class FakePreparedSpeech:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class PreparingSpeech:
    def __init__(self):
        self.events = []
        self.prepared = threading.Event()
        self.styles = []

    def say_thinking_prelude(self):
        self.events.append("prelude:start")
        self.prepared.wait(timeout=1)
        self.events.append("prelude:end")
        return True

    def prepare(self, _text, style):
        self.events.append("prepare")
        self.styles.append(style)
        self.prepared.set()
        return FakePreparedSpeech()

    def play_prepared(self, _prepared):
        self.events.append("play")
        return True


class NoticingSpeech:
    def __init__(self, notice):
        self.notice = notice
        self.local_speech = RecordingSpeech()

    def prepare(self, _text, _style):
        return FakePreparedSpeech()

    def play_prepared(self, prepared):
        prepared.close()
        return True

    def consume_notice(self):
        notice = self.notice
        self.notice = None
        return notice


class RaisingSpeech:
    def say(self, _text, _style=SpeechStyle.CONVERSATIONAL):
        raise RuntimeError("private Vector transport detail")


class OfflineNoticeTests(unittest.TestCase):
    def test_unreliable_provider_text_is_replaced_before_tts(self):
        unsafe = "Error: private provider response"
        speech = RecordingSpeech()

        completed = respond_and_speak(
            Agent(ScriptedProvider(unsafe)),
            speech,
            "Welche Information liegt vor?",
        )

        self.assertTrue(completed)
        self.assertEqual([SAFE_PROVIDER_REPLACEMENT], speech.messages)
        self.assertNotIn(unsafe, speech.messages)

    def test_cloud_outage_speaks_notice_before_local_answer(self):
        model = FallbackProvider(
            ScriptedProvider(RuntimeError("offline")),
            ScriptedProvider("Die lokale Antwort ist verfügbar."),
        )
        speech = RecordingSpeech()

        completed = respond_and_speak(Agent(model), speech, "Bist du erreichbar?")

        self.assertTrue(completed)
        self.assertEqual(
            [CLOUD_OFFLINE_NOTICE, "Die lokale Antwort ist verfügbar."],
            speech.messages,
        )

    def test_same_outage_is_announced_only_once(self):
        model = FallbackProvider(
            ScriptedProvider(RuntimeError("offline"), RuntimeError("offline")),
            ScriptedProvider("Lokale Antwort eins.", "Lokale Antwort zwei."),
        )
        speech = RecordingSpeech()
        agent = Agent(model)

        respond_and_speak(agent, speech, "Erste Frage.")
        respond_and_speak(agent, speech, "Zweite Frage.")

        self.assertEqual(1, speech.messages.count(CLOUD_OFFLINE_NOTICE))
        self.assertEqual("Lokale Antwort zwei.", speech.messages[-1])

    def test_total_failure_uses_honest_shorter_notice(self):
        model = FallbackProvider(
            ScriptedProvider(RuntimeError("cloud offline")),
            ScriptedProvider(RuntimeError("local offline")),
        )
        speech = RecordingSpeech()

        completed = respond_and_speak(Agent(model), speech, "Kannst du antworten?")

        self.assertFalse(completed)
        self.assertEqual([PROVIDER_OFFLINE_NOTICE], speech.messages)

    def test_repeated_total_failure_does_not_repeat_offline_notice(self):
        model = FallbackProvider(
            ScriptedProvider(RuntimeError("cloud one"), RuntimeError("cloud two")),
            ScriptedProvider(RuntimeError("local one"), RuntimeError("local two")),
        )
        speech = RecordingSpeech()
        agent = Agent(model)

        respond_and_speak(agent, speech, "Erste Frage.")
        respond_and_speak(agent, speech, "Zweite Frage.")

        self.assertEqual(1, speech.messages.count(PROVIDER_OFFLINE_NOTICE))

    def test_conversation_can_continue_after_complete_model_outage(self):
        model = FallbackProvider(
            ScriptedProvider(
                RuntimeError("cloud offline"),
                "Der nächste Turn funktioniert wieder.",
            ),
            ScriptedProvider(RuntimeError("local offline")),
        )
        speech = RecordingSpeech()
        agent = Agent(model)

        first = respond_and_speak(agent, speech, "Erste Frage.")
        second = respond_and_speak(agent, speech, "Zweite Frage.")

        self.assertFalse(first)
        self.assertTrue(second)
        self.assertEqual(1, speech.messages.count(PROVIDER_OFFLINE_NOTICE))
        self.assertEqual(1, speech.messages.count(PROVIDER_RECOVERY_NOTICE))
        self.assertEqual(
            "Der nächste Turn funktioniert wieder.",
            speech.messages[-1],
        )

    def test_primary_recovery_is_announced_only_once(self):
        model = FallbackProvider(
            ScriptedProvider(
                RuntimeError("offline"),
                "Cloud wieder verfügbar.",
                "Cloud bleibt verfügbar.",
            ),
            ScriptedProvider("Lokale Antwort."),
        )
        speech = RecordingSpeech()
        agent = Agent(model)

        for question in ("Runde eins?", "Runde zwei?", "Runde drei?"):
            respond_and_speak(agent, speech, question)

        self.assertEqual(1, speech.messages.count(PROVIDER_RECOVERY_NOTICE))

    def test_simultaneous_cloud_fallbacks_use_one_offline_notice(self):
        model = FallbackProvider(
            ScriptedProvider(RuntimeError("cloud offline")),
            ScriptedProvider("Lokale Antwort."),
        )
        speech = NoticingSpeech(SpeechProviderNotice.LOCAL_FALLBACK)

        completed = respond_and_speak(Agent(model), speech, "Bist du da?")

        self.assertTrue(completed)
        self.assertEqual([CLOUD_OFFLINE_NOTICE], speech.local_speech.messages)
        self.assertNotIn(TTS_OFFLINE_NOTICE, speech.local_speech.messages)

    def test_tts_fallback_uses_one_local_notice(self):
        speech = NoticingSpeech(SpeechProviderNotice.LOCAL_FALLBACK)
        agent = Agent(ScriptedProvider("Antwort ist verfügbar."))

        completed = respond_and_speak(agent, speech, "Bist du da?")

        self.assertTrue(completed)
        self.assertEqual([TTS_OFFLINE_NOTICE], speech.local_speech.messages)

    def test_tts_recovery_is_announced_once_through_local_voice(self):
        speech = NoticingSpeech(SpeechProviderNotice.CLOUD_RECOVERED)
        agent = Agent(ScriptedProvider("Cloud-Stimme antwortet wieder."))

        completed = respond_and_speak(agent, speech, "Bist du wieder da?")

        self.assertTrue(completed)
        self.assertEqual(
            [PROVIDER_RECOVERY_NOTICE],
            speech.local_speech.messages,
        )

    def test_vector_delivery_exception_stays_inside_response_boundary(self):
        agent = Agent(ScriptedProvider("Antwort bleibt erhalten."))

        with patch("builtins.print") as output:
            completed = respond_and_speak(agent, RaisingSpeech(), "Hallo?")

        self.assertFalse(completed)
        printed = " ".join(str(call) for call in output.call_args_list)
        self.assertIn(VECTOR_UNAVAILABLE_MESSAGE, printed)
        self.assertNotIn("private Vector transport detail", printed)

    def test_recovery_allows_a_later_outage_notice_again(self):
        model = FallbackProvider(
            ScriptedProvider(
                RuntimeError("offline"),
                "Cloud wieder verfügbar.",
                RuntimeError("offline again"),
            ),
            ScriptedProvider("Lokal eins.", "Lokal zwei."),
        )
        speech = RecordingSpeech()
        agent = Agent(model)

        for question in ("Runde eins?", "Runde zwei?", "Runde drei?"):
            respond_and_speak(agent, speech, question)

        self.assertEqual(2, speech.messages.count(CLOUD_OFFLINE_NOTICE))

    def test_ordinary_supportive_turn_selects_supportive_speech(self):
        speech = RecordingSpeech()
        agent = Agent(ScriptedProvider("Das klingt schwer. Wir gehen ruhig vor."))

        completed = respond_and_speak(
            agent,
            speech,
            "Ich bin traurig und überfordert.",
        )

        self.assertTrue(completed)
        self.assertEqual([SpeechStyle.SUPPORTIVE], speech.styles)

    def test_ordinary_risk_turn_selects_cautious_speech(self):
        speech = RecordingSpeech()
        agent = Agent(ScriptedProvider("Das ist unsicher. Prüfe es bitte zuerst."))

        completed = respond_and_speak(agent, speech, "Ist das gefährlich?")

        self.assertTrue(completed)
        self.assertEqual([SpeechStyle.CAUTIOUS], speech.styles)

    def test_answer_audio_is_prepared_before_thinking_prelude_finishes(self):
        speech = PreparingSpeech()
        agent = Agent(ScriptedProvider("Das klingt schwer. Wir gehen ruhig vor."))

        completed = respond_and_speak(agent, speech, "Ich bin traurig.")

        self.assertTrue(completed)
        self.assertLess(
            speech.events.index("prepare"),
            speech.events.index("prelude:end"),
        )
        self.assertEqual("play", speech.events[-1])
        self.assertEqual([SpeechStyle.SUPPORTIVE], speech.styles)


if __name__ == "__main__":
    unittest.main()
