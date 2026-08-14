import unittest

from brain.agent import Agent
from brain.context import ChatMessage, ConversationContext


class RecordingLanguageModel:
    def __init__(self, response: str):
        self.response = response
        self.received_messages: tuple[ChatMessage, ...] = ()

    def generate(self, messages):
        self.received_messages = tuple(messages)
        return self.response


class RecordingMemoryStore:
    def search(self, query, limit=5):
        from memory.models import MemoryEntry

        return (
            MemoryEntry(
                id=7,
                content="Andres Lieblingsprojekt heißt Vector Office AI.",
                category="fact",
                source="user-confirmed",
                created_at="2026-08-14 12:00:00",
            ),
        )


class AgentTests(unittest.TestCase):
    def test_respond_sends_context_and_stores_response(self):
        model = RecordingLanguageModel("Guten Tag!")
        agent = Agent(model)

        response = agent.respond("  Hallo Vector  ")

        self.assertEqual("Guten Tag!", response)
        self.assertEqual("system", model.received_messages[0].role)
        self.assertEqual("Hallo Vector", model.received_messages[1].content)
        self.assertEqual("assistant", agent.context.history[-1].role)
        self.assertEqual("Guten Tag!", agent.context.history[-1].content)

    def test_respond_rejects_empty_user_text(self):
        agent = Agent(RecordingLanguageModel("Antwort"))

        with self.assertRaises(ValueError):
            agent.respond("   ")

    def test_respond_includes_relevant_long_term_memory(self):
        model = RecordingLanguageModel("Vector Office AI")
        agent = Agent(model, memory_store=RecordingMemoryStore())

        agent.respond("Wie heißt mein Lieblingsprojekt?")

        self.assertEqual("system", model.received_messages[0].role)
        self.assertIn(
            "Vector Office AI",
            model.received_messages[0].content,
        )

    def test_respond_rejects_empty_model_response(self):
        agent = Agent(RecordingLanguageModel("   "))

        with self.assertRaises(RuntimeError):
            agent.respond("Hallo")

    def test_context_limits_history(self):
        context = ConversationContext(max_history_messages=2)
        context.add_user_message("Eins")
        context.add_assistant_message("Zwei")
        context.add_user_message("Drei")

        self.assertEqual(
            ("Drei",),
            tuple(message.content for message in context.history),
        )


if __name__ == "__main__":
    unittest.main()
