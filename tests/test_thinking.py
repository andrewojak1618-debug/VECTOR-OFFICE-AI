import threading
import unittest

from application.thinking import generate_with_thinking


class CoordinatedAgent:
    def __init__(self, events, model_started, allow_model_finish, model_finished):
        self.events = events
        self.model_started = model_started
        self.allow_model_finish = allow_model_finish
        self.model_finished = model_finished

    def respond(self, user_text):
        self.events.append("model:start")
        self.model_started.set()
        self.allow_model_finish.wait(timeout=1)
        self.events.append("model:end")
        self.model_finished.set()
        return f"Antwort auf {user_text}"


class CoordinatedSpeech:
    def __init__(self, events, model_started, allow_model_finish, model_finished):
        self.events = events
        self.model_started = model_started
        self.allow_model_finish = allow_model_finish
        self.model_finished = model_finished

    def say_thinking_prelude(self):
        self.model_started.wait(timeout=1)
        self.events.append("prelude:start")
        self.allow_model_finish.set()
        self.model_finished.wait(timeout=1)
        self.events.append("prelude:end")
        return True


class ThinkingCoordinatorTests(unittest.TestCase):
    def test_model_generation_overlaps_prelude_before_answer_returns(self):
        events = []
        model_started = threading.Event()
        allow_model_finish = threading.Event()
        model_finished = threading.Event()
        agent = CoordinatedAgent(
            events,
            model_started,
            allow_model_finish,
            model_finished,
        )
        speech = CoordinatedSpeech(
            events,
            model_started,
            allow_model_finish,
            model_finished,
        )

        answer = generate_with_thinking(agent, speech, "Testfrage")

        self.assertEqual("Antwort auf Testfrage", answer)
        self.assertEqual(
            ["model:start", "prelude:start", "model:end", "prelude:end"],
            events,
        )

    def test_missing_optional_prelude_keeps_response_available(self):
        agent = type("Agent", (), {"respond": lambda self, text: "Antwort"})()

        self.assertEqual("Antwort", generate_with_thinking(agent, object(), "Frage"))


if __name__ == "__main__":
    unittest.main()
