import unittest

from diagnostics.knowledge_vector import (
    _answer_has_expected_fact,
    _limit_to_two_sentences,
    _sentence_count,
)


class KnowledgeVectorDiagnosticTests(unittest.TestCase):
    def test_answer_is_limited_to_two_short_sentences(self):
        answer = _limit_to_two_sentences(
            "Der Wert ist 0,35. Das ist der beste Kompromiss. Ein dritter Satz."
        )

        self.assertEqual(
            "Der Wert ist 0,35. Das ist der beste Kompromiss.",
            answer,
        )
        self.assertEqual(2, _sentence_count(answer))

    def test_expected_decimal_value_accepts_german_or_technical_notation(self):
        self.assertTrue(_answer_has_expected_fact("Der Wert beträgt 0,35."))
        self.assertTrue(_answer_has_expected_fact("The value is 0.35."))
        self.assertFalse(_answer_has_expected_fact("Der Wert ist unbekannt."))


if __name__ == "__main__":
    unittest.main()
