import unittest

from brain.emotions import (
    MAX_STANCE_INTENSITY,
    MAX_TRANSITION_HISTORY,
    ConversationStance,
    EmotionalStateModel,
    ExpressionCue,
)


class EmotionalStateModelTests(unittest.TestCase):
    def test_initial_state_is_neutral_and_explicitly_simulated(self):
        model = EmotionalStateModel()

        self.assertEqual(ConversationStance.NEUTRAL, model.state.stance)
        self.assertEqual(0, model.state.intensity)
        self.assertIn("Simulierte Gesprächshaltung", model.prompt_guidance())
        self.assertIn("niemals", model.prompt_guidance())

    def test_supportive_signal_creates_traceable_bounded_transition(self):
        model = EmotionalStateModel()

        transition = model.observe("Ich bin heute traurig und überfordert.")

        self.assertTrue(transition.changed)
        self.assertEqual(ConversationStance.SUPPORTIVE, transition.current.stance)
        self.assertEqual(1, transition.current.intensity)
        self.assertEqual("keyword:supportive", transition.current.reason)
        self.assertNotIn("traurig", transition.current.reason)

    def test_repeated_signal_never_exceeds_maximum_intensity(self):
        model = EmotionalStateModel()

        for _ in range(5):
            model.observe("Ich habe Sorge.")

        self.assertEqual(MAX_STANCE_INTENSITY, model.state.intensity)

    def test_neutral_turn_reduces_state_gradually(self):
        model = EmotionalStateModel()
        model.observe("Ich bin traurig.")
        model.observe("Ich bin noch immer traurig.")

        first_decay = model.observe("Wie spät ist es?")
        second_decay = model.observe("Nenne mir die Uhrzeit.")

        self.assertEqual(1, first_decay.current.intensity)
        self.assertEqual(ConversationStance.NEUTRAL, second_decay.current.stance)
        self.assertEqual(0, second_decay.current.intensity)

    def test_support_need_takes_priority_over_reflection(self):
        model = EmotionalStateModel()

        model.observe("Ich bin traurig und frage nach dem Sinn des Lebens.")

        self.assertEqual(ConversationStance.SUPPORTIVE, model.state.stance)
        self.assertEqual(ExpressionCue.SUPPORTIVE, model.state.expression_cue)

    def test_reflective_state_prepares_non_executable_expression_cue(self):
        model = EmotionalStateModel()

        model.observe("Was bedeutet Freiheit philosophisch?")

        self.assertEqual(ConversationStance.REFLECTIVE, model.state.stance)
        self.assertEqual(ExpressionCue.REFLECTIVE, model.state.expression_cue)
        self.assertIn("aktiven Verben", model.prompt_guidance())
        self.assertIn("greifbaren Gedanken", model.prompt_guidance())
        self.assertIn("unter 18 Wörtern", model.prompt_guidance())

    def test_transition_history_is_bounded_and_contains_no_user_text(self):
        model = EmotionalStateModel()

        for _ in range(MAX_TRANSITION_HISTORY + 5):
            model.observe("Diese Sorge ist privat.")

        self.assertEqual(MAX_TRANSITION_HISTORY, len(model.history))
        reasons = tuple(item.current.reason for item in model.history)
        self.assertNotIn("privat", " ".join(reasons))

    def test_empty_observation_is_rejected(self):
        with self.assertRaises(ValueError):
            EmotionalStateModel().observe("   ")


if __name__ == "__main__":
    unittest.main()
