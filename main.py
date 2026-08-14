from brain.agent import Agent
from brain.ollama_runtime import OllamaRuntime
from brain.providers import create_language_model
from config.settings import settings
from memory.database import SQLiteMemoryStore
from vector.client import VectorClient
from vector.sdk_client import VectorSDKClient
from vector.speech import VectorSpeech


def run_conversation(agent: Agent, speech: VectorSpeech) -> None:
    print()
    print("Conversation started.")
    print("Commands: /remember, /memories, /forget, /clear, /exit")

    while True:
        print()

        try:
            user_text = input("Du: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print("Conversation ended.")
            return

        if not user_text:
            continue

        command = user_text.lower()

        if command == "/exit":
            print("Conversation ended.")
            return

        if command == "/clear":
            agent.context.clear()
            print("Conversation context cleared.")
            continue

        if command.startswith("/remember "):
            if agent.memory_store is None:
                print("Long-term memory is unavailable.")
                continue

            memory = agent.memory_store.remember(user_text[10:])
            print(f"Memory {memory.id} saved.")
            continue

        if command == "/memories":
            if agent.memory_store is None:
                print("Long-term memory is unavailable.")
                continue

            memories = agent.memory_store.list_memories()

            if not memories:
                print("No long-term memories saved.")
            else:
                for memory in memories:
                    print(f"[{memory.id}] {memory.content}")
            continue

        if command.startswith("/forget "):
            if agent.memory_store is None:
                print("Long-term memory is unavailable.")
                continue

            try:
                memory_id = int(user_text[8:].strip())
            except ValueError:
                print("Usage: /forget ID")
                continue

            if agent.memory_store.forget(memory_id):
                print(f"Memory {memory_id} deleted.")
            else:
                print(f"Memory {memory_id} was not found.")
            continue

        print("Thinking...")

        try:
            answer = agent.respond(user_text)
        except (RuntimeError, ValueError) as exc:
            print(f"Brain request failed: {exc}")
            continue

        print(f"Vector: {answer}")

        if not speech.say(answer):
            print("Vector could not play the response.")


def main():
    print("=" * 50)
    print(f"{settings.APP_NAME} v{settings.VERSION}")
    print("=" * 50)

    print(f"Robot:   {settings.VECTOR_NAME}")
    print(f"WirePod: {settings.WIREPOD_HOST}")

    provider = settings.LLM_PROVIDER.lower().strip()
    fallback_provider = settings.LLM_FALLBACK_PROVIDER.lower().strip()
    needs_ollama = (
        provider == "ollama"
        or (provider == "openai" and fallback_provider == "ollama")
    )

    if needs_ollama:
        print()
        print("Checking local Ollama service...")
        ollama_ready = OllamaRuntime(
            base_url=settings.OLLAMA_HOST,
            executable=settings.OLLAMA_EXECUTABLE,
        ).ensure_available()

        if not ollama_ready and provider == "ollama":
            print("Ollama is required as the active LLM provider. [ERROR]")
            return

        if not ollama_ready:
            print("Continuing with OpenAI without local fallback.")

    print()
    print("Checking WirePod connection...")

    wirepod = VectorClient(settings.WIREPOD_HOST)

    if not wirepod.check_wirepod():
        print("WirePod is not reachable. [ERROR]")
        return

    print("WirePod is online. [OK]")

    print()
    print("Starting Vector SDK test...")

    vector = VectorSDKClient(settings.VECTOR_SERIAL)

    if vector.test_connection():
        print()
        print(f"LLM provider: {settings.LLM_PROVIDER}")

        speech = VectorSpeech(
            vector,
            voice=settings.TTS_VOICE,
            volume=settings.TTS_VOLUME,
        )
        memory_store = SQLiteMemoryStore(settings.MEMORY_DB_PATH)
        agent = Agent(
            create_language_model(settings),
            memory_store=memory_store,
            memory_context_limit=settings.MEMORY_CONTEXT_LIMIT,
        )
        run_conversation(agent, speech)


if __name__ == "__main__":
    main()
