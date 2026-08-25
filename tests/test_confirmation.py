"""Tests for conservative natural yes/no classification."""

import unittest

from application.confirmation import (
    ConfirmationDecision,
    classify_confirmation,
)


class ConfirmationDecisionTests(unittest.TestCase):
    def test_natural_yes_sentence_is_confirmed(self):
        decision = classify_confirmation("Ja, den Ordner bitte öffnen.")

        self.assertEqual(ConfirmationDecision.CONFIRM, decision)

    def test_negative_word_overrides_leading_yes(self):
        decision = classify_confirmation("Ja, doch nicht ausführen.")

        self.assertEqual(ConfirmationDecision.REJECT, decision)

    def test_abort_sentence_is_cancelled(self):
        decision = classify_confirmation("Bitte die Antwort verwerfen.")

        self.assertEqual(ConfirmationDecision.CANCEL, decision)

    def test_unrelated_sentence_grants_no_authority(self):
        decision = classify_confirmation("Vielleicht später.")

        self.assertEqual(ConfirmationDecision.UNKNOWN, decision)


if __name__ == "__main__":
    unittest.main()
