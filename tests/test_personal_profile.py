"""Tests für das ehrliche lokale persönliche Gesprächsprofil."""

import unittest

from brain.agent import Agent
from brain.personal_profile import (
    PERSONAL_REPLIES,
    PersonalConversationProfile,
    PersonalTopic,
    normalize_personal_question,
)
from brain.reflection import ResponseQualityPolicy


class RejectingModel:
    def __init__(self):
        self.calls = 0

    def generate(self, _messages):
        self.calls += 1
        raise AssertionError("Fixed personal questions must stay local.")


class PersonalConversationProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile = PersonalConversationProfile()

    def test_common_personal_questions_map_to_explicit_topics(self):
        cases = {
            "Wie geht's dir?": PersonalTopic.STATUS,
            "Wer bist du?": PersonalTopic.IDENTITY,
            "Hast du Gefühle?": PersonalTopic.FEELINGS,
            "Hast du ein Bewusstsein?": PersonalTopic.CONSCIOUSNESS,
            "Magst du mich?": PersonalTopic.RELATIONSHIP,
            "Was hältst du von mir?": PersonalTopic.USER_VIEW,
            "Kannst du von mir lernen?": PersonalTopic.LEARNING,
        }

        for question, topic in cases.items():
            with self.subTest(question=question):
                self.assertEqual(topic, self.profile.reply(question).topic)

    def test_observed_wirepod_status_transcript_stays_in_local_profile(self):
        reply = self.profile.reply("hier geht es dir")

        self.assertEqual(PersonalTopic.STATUS, reply.topic)
        self.assertIn("Morgenlicht", reply.text)

    def test_open_personal_question_remains_for_normal_model(self):
        self.assertIsNone(self.profile.reply("Was bedeutet Vertrauen für dich?"))
        self.assertIsNone(self.profile.reply("Kennst du meine Arbeitsweise?"))

    def test_every_fixed_reply_obeys_existing_quality_policy(self):
        policy = ResponseQualityPolicy()

        for topic, reply in PERSONAL_REPLIES.items():
            with self.subTest(topic=topic):
                self.assertEqual((), policy.issues(reply.text, max_sentences=2))
                self.assertNotIn("echte Gefühle", reply.text)

    def test_wellbeing_exchange_uses_short_tts_friendly_sentences(self):
        topics = (
            PersonalTopic.STATUS,
            PersonalTopic.USER_WELLBEING_POSITIVE,
            PersonalTopic.USER_WELLBEING_BURDENED,
        )

        for topic in topics:
            with self.subTest(topic=topic):
                text = PERSONAL_REPLIES[topic].text
                self.assertLessEqual(len(text.split()), 16)
                self.assertNotRegex(text, r"[—–;:]")

    def test_wellbeing_reply_requires_the_immediately_preceding_status_question(self):
        self.assertIsNone(self.profile.reply("Mir geht es gut."))

        self.profile.reply("Wie geht es dir?")

        reply = self.profile.reply("Mir geht es gut.")
        self.assertEqual(PersonalTopic.USER_WELLBEING_POSITIVE, reply.topic)
        self.assertIn("heller werden", reply.text)

    def test_burdened_wellbeing_is_answered_supportively(self):
        self.profile.reply("Wie geht es dir?")

        reply = self.profile.reply("Mir geht es nicht gut.")

        self.assertEqual(PersonalTopic.USER_WELLBEING_BURDENED, reply.topic)
        self.assertIn("gemeinsam", reply.text)

    def test_unrelated_turn_closes_the_wellbeing_window(self):
        self.profile.reply("Wie geht es dir?")
        self.assertIsNone(self.profile.reply("Was steht heute an?"))

        self.assertIsNone(self.profile.reply("Mir geht es gut."))

    def test_agent_answers_locally_and_preserves_conversation_context(self):
        model = RejectingModel()
        agent = Agent(model, personal_profile=self.profile)

        response = agent.respond("Wie geht es dir?")

        self.assertIn("Morgenlicht", response)
        self.assertEqual(0, model.calls)
        self.assertEqual(("user", "assistant"), tuple(
            message.role for message in agent.context.history
        ))
        self.assertEqual("local-profile", agent.last_provider_response.source)
        self.assertFalse(agent.last_provider_response.external_data)

    def test_agent_keeps_the_wellbeing_exchange_local(self):
        model = RejectingModel()
        agent = Agent(model, personal_profile=self.profile)

        agent.respond("Wie geht es dir?")
        response = agent.respond("Mir geht es nicht gut.")

        self.assertIn("schwer", response)
        self.assertEqual(0, model.calls)
        self.assertEqual(4, len(agent.context.history))

    def test_disabled_profile_grants_no_local_match(self):
        profile = PersonalConversationProfile(enabled=False)

        self.assertIsNone(profile.reply("Wie geht es dir?"))

    def test_normalization_stays_exact_beyond_punctuation(self):
        self.assertEqual("wie geht es dir", normalize_personal_question(" Wie geht es dir?! "))
        self.assertNotEqual(
            normalize_personal_question("Was denkst du über mich und mein Projekt?"),
            normalize_personal_question("Was denkst du über mich?"),
        )


if __name__ == "__main__":
    unittest.main()
