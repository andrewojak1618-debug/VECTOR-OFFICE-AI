import unittest

from brain.reflection import (
    ReflectionMode,
    ReflectionPolicy,
    ResponseIssue,
    ResponseQualityPolicy,
)


class ReflectionPolicyTests(unittest.TestCase):
    def test_philosophical_topic_activates_compact_reflection(self):
        plan = ReflectionPolicy().prepare(
            "Welche Bedeutung hat Freiheit für Verantwortung?"
        )

        self.assertTrue(plan.active)
        self.assertEqual(ReflectionMode.REFLECTIVE, plan.mode)
        self.assertIn("Tatsachen", plan.guidance)
        self.assertIn("mögliche Sichtweise", plan.guidance)
        self.assertIn("höchstens zwei Sätzen", plan.guidance)
        self.assertIn("eigenständiges Nachdenken", plan.guidance)
        self.assertIn("keine abstrakte Aufzählung", plan.guidance)
        self.assertIn("greifbaren Kerngedanken", plan.guidance)
        self.assertIn("Lexikondefinition", plan.guidance)
        self.assertIn("unter 18 Wörtern", plan.guidance)
        self.assertEqual(2, plan.max_sentences)

    def test_ordinary_question_keeps_direct_mode(self):
        plan = ReflectionPolicy().prepare("Wie spät ist es?")

        self.assertFalse(plan.active)
        self.assertEqual(ReflectionMode.DIRECT, plan.mode)

    def test_explicit_detail_request_relaxes_only_the_sentence_limit(self):
        plan = ReflectionPolicy().prepare(
            "Erkläre ausführlich, was Freiheit philosophisch bedeutet."
        )

        self.assertTrue(plan.active)
        self.assertEqual(8, plan.max_sentences)

    def test_optional_layer_can_be_disabled(self):
        plan = ReflectionPolicy(enabled=False).prepare(
            "Was ist der Sinn des Lebens?"
        )

        self.assertFalse(plan.active)
        self.assertEqual("reflection-disabled", plan.reason)

    def test_invalid_flag_and_empty_input_are_rejected(self):
        with self.assertRaises(TypeError):
            ReflectionPolicy(enabled=1)
        with self.assertRaises(ValueError):
            ReflectionPolicy().prepare(" ")


class ResponseQualityPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = ResponseQualityPolicy()

    def test_claimed_human_emotion_is_detected(self):
        issues = self.policy.issues("Ich fühle echte Trauer mit dir.")

        self.assertIn(ResponseIssue.CLAIMED_EMOTION, issues)

    def test_transparent_absence_of_feelings_is_allowed(self):
        issues = self.policy.issues(
            "Ich habe keine eigenen Gefühle, kann aber behutsam antworten."
        )

        self.assertEqual((), issues)

    def test_false_certainty_and_lecturing_are_detected(self):
        issues = self.policy.issues(
            "Das ist garantiert richtig; du musst einfach besser zuhören."
        )

        self.assertIn(ResponseIssue.FALSE_CERTAINTY, issues)
        self.assertIn(ResponseIssue.LECTURING, issues)

    def test_apology_formula_and_long_response_are_detected(self):
        issues = self.policy.issues(
            "Es tut mir leid. Das klingt schwer. Wir betrachten den nächsten Schritt."
        )

        self.assertIn(ResponseIssue.CLAIMED_EMOTION, issues)
        self.assertIn(ResponseIssue.TOO_LONG, issues)

    def test_correction_uses_only_issue_codes(self):
        guidance = self.policy.correction_guidance(
            (ResponseIssue.CLAIMED_EMOTION,)
        )

        self.assertIn("claimed_emotion", guidance)
        self.assertIn("Es tut mir leid", guidance)
        self.assertIn("Das klingt belastend", guidance)
        self.assertIn("Erwähne diese Korrektur nicht", guidance)

    def test_sentence_limit_keeps_complete_leading_sentences(self):
        compacted = self.policy.limit_sentences(
            "Erster Satz. Zweiter Satz! Dritter Satz?",
            2,
        )

        self.assertEqual("Erster Satz. Zweiter Satz!", compacted)

    def test_sentence_limit_rejects_non_positive_maximum(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            self.policy.limit_sentences("Ein Satz.", 0)


if __name__ == "__main__":
    unittest.main()
