from typing import Protocol, Sequence

from brain.context import ChatMessage, ConversationContext


class LanguageModel(Protocol):
    def generate(self, messages: Sequence[ChatMessage]) -> str:
        """Generate an assistant response for the supplied conversation."""


class Agent:
    def __init__(
        self,
        language_model: LanguageModel,
        context: ConversationContext | None = None,
    ):
        self.language_model = language_model
        self.context = context or ConversationContext()

    def respond(self, user_text: str) -> str:
        normalized_text = user_text.strip()

        if not normalized_text:
            raise ValueError("User text must not be empty.")

        self.context.add_user_message(normalized_text)
        response = self.language_model.generate(self.context.messages()).strip()

        if not response:
            raise RuntimeError("Language model returned an empty response.")

        self.context.add_assistant_message(response)
        return response
