"""Spoken local notices for cloud and complete provider outages."""

import unittest

from application.conversation import (
    CLOUD_OFFLINE_NOTICE,
    PROVIDER_OFFLINE_NOTICE,
    respond_and_speak,
)
from brain.agent import Agent
from brain.providers import FallbackProvider


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

    def say(self, text):
        self.messages.append(text)
        return True


class OfflineNoticeTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
