import unittest

from brain.agent import Agent
from brain.context import ChatMessage


class ExampleLanguageModel:
    def __init__(self, response):
        self.response = response
        self.messages: tuple[ChatMessage, ...] = ()

    def generate(self, messages):
        self.messages = tuple(messages)
        return self.response


class PersonalityDialogueTests(unittest.TestCase):
    def test_supportive_dialogue_is_warm_without_claiming_feelings(self):
        model = ExampleLanguageModel(
            "Das klingt nach einer belastenden Situation. Wir können den "
            "nächsten Schritt gemeinsam ruhig sortieren."
        )

        response = Agent(model).respond("Ich bin gerade traurig und überfordert.")

        self.assertIn("supportive", model.messages[0].content)
        self.assertNotIn("Ich fühle", response)
        self.assertEqual(2, response.count("."))

    def test_philosophical_dialogue_marks_fact_and_possible_perspective(self):
        model = ExampleLanguageModel(
            "Faktisch setzt Freiheit Handlungsspielraum voraus. Eine mögliche "
            "Sichtweise ist, dass sie erst durch Verantwortung Bedeutung gewinnt."
        )

        response = Agent(model).respond(
            "Welche Bedeutung hat Freiheit für Verantwortung?"
        )

        system = model.messages[0].content
        self.assertIn("Tatsachen von Deutung", system)
        self.assertIn("mögliche Sichtweise", response)
        self.assertEqual(2, response.count("."))

    def test_uncertain_dialogue_states_the_limit_without_overstatement(self):
        model = ExampleLanguageModel(
            "Soweit die verfügbaren Angaben reichen, ist diese Deutung plausibel. "
            "Sicher entscheiden lässt sie sich ohne weitere Quellen nicht."
        )

        response = Agent(model).respond("Diese Aussage ist unsicher, oder?")

        self.assertIn("cautious", model.messages[0].content)
        self.assertIn("nicht", response)
        self.assertNotIn("garantiert", response.casefold())


if __name__ == "__main__":
    unittest.main()
