from brain.agent import Agent
from brain.ollama_runtime import OllamaRuntime
from brain.providers import OllamaProvider, create_language_model
from config.settings import settings
from memory.database import SQLiteMemoryStore
from memory.library import SQLiteKnowledgeLibrary
from vector.client import VectorClient
from vector.sdk_client import VectorSDKClient
from vector.speech import VectorSpeech
from voice.wirepod_input import WirePodTranscriptListener


VOICE_EXIT_PHRASES = {
    "gespräch beenden",
    "programm beenden",
    "vector beenden",
}


def respond_and_speak(
    agent: Agent,
    speech: VectorSpeech,
    user_text: str,
) -> bool:
    print("Thinking...")

    try:
        answer = agent.respond(user_text)
    except (RuntimeError, ValueError) as exc:
        print(f"Brain request failed: {exc}")
        return False

    print(f"Vector: {answer}")

    if not speech.say(answer):
        print("Vector could not play the response.")
        return False

    return True


def run_conversation(agent: Agent, speech: VectorSpeech) -> None:
    print()
    print("Conversation started.")
    print(
        "Commands: /remember, /memories, /forget, /learn, "
        "/documents, /forget-document, /clear, /exit"
    )

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

        if command.startswith("/learn "):
            library = getattr(agent, "knowledge_library", None)
            if library is None:
                print("Document library is unavailable.")
                continue

            try:
                result = library.import_document(user_text[7:])
            except (OSError, ValueError) as exc:
                print(f"Document import failed: {exc}")
                continue

            state = "imported" if result.changed else "already current"
            print(
                f"Document {result.document.id} {state} "
                f"({result.chunk_count} sections): {result.document.title}"
            )
            continue

        if command == "/documents":
            library = getattr(agent, "knowledge_library", None)
            if library is None:
                print("Document library is unavailable.")
                continue

            documents = library.list_documents()
            if not documents:
                print("No documents imported.")
            else:
                for document in documents:
                    print(
                        f"[{document.id}] {document.title} "
                        f"({document.source_path})"
                    )
            continue

        if command.startswith("/forget-document "):
            library = getattr(agent, "knowledge_library", None)
            if library is None:
                print("Document library is unavailable.")
                continue

            try:
                document_id = int(user_text[17:].strip())
            except ValueError:
                print("Usage: /forget-document ID")
                continue

            if library.forget_document(document_id):
                print(f"Document {document_id} deleted.")
            else:
                print(f"Document {document_id} was not found.")
            continue

        respond_and_speak(agent, speech, user_text)


def run_voice_conversation(
    agent: Agent,
    speech: VectorSpeech,
    listener: WirePodTranscriptListener,
    listen_timeout: float = 120.0,
    max_turns: int | None = None,
) -> None:
    print()
    print("WirePod voice conversation started.")
    print("Say 'Hey Vector' followed by your question.")
    print("Say 'Vector beenden' to end the session.")
    listener.prime()
    completed_turns = 0

    while max_turns is None or completed_turns < max_turns:
        print()
        print("Listening...")

        try:
            event = listener.wait_for_transcript(listen_timeout)
        except RuntimeError as exc:
            print(f"Voice input failed: {exc}")
            return

        if event is None:
            print("No speech recognized before the timeout.")
            continue

        user_text = event.text.strip()
        print(f"Du: {user_text}")

        if user_text.casefold() in VOICE_EXIT_PHRASES:
            print("Conversation ended.")
            return

        respond_and_speak(agent, speech, user_text)
        completed_turns += 1


def main():
    print("=" * 50)
    print(f"{settings.APP_NAME} v{settings.VERSION}")
    print("=" * 50)

    print(f"Robot:   {settings.VECTOR_NAME}")
    print(f"WirePod: {settings.WIREPOD_HOST}")

    provider = settings.LLM_PROVIDER.lower().strip()
    fallback_provider = settings.LLM_FALLBACK_PROVIDER.lower().strip()
    input_mode = settings.INPUT_MODE.lower().strip()
    local_voice_required = (
        input_mode == "wirepod"
        and provider == "openai"
        and not settings.VOICE_ALLOW_CLOUD
    )
    needs_ollama = (
        provider == "ollama"
        or (provider == "openai" and fallback_provider == "ollama")
        or local_voice_required
    )

    if needs_ollama:
        print()
        print("Checking local Ollama service...")
        ollama_ready = OllamaRuntime(
            base_url=settings.OLLAMA_HOST,
            executable=settings.OLLAMA_EXECUTABLE,
        ).ensure_available()

        if not ollama_ready and (provider == "ollama" or local_voice_required):
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
        knowledge_library = SQLiteKnowledgeLibrary(settings.MEMORY_DB_PATH)
        if local_voice_required:
            print("Voice privacy: using local Ollama (cloud disabled).")
            language_model = OllamaProvider(
                base_url=settings.OLLAMA_HOST,
                model=settings.OLLAMA_MODEL,
            )
        else:
            language_model = create_language_model(settings)

        agent = Agent(
            language_model,
            memory_store=memory_store,
            memory_context_limit=settings.MEMORY_CONTEXT_LIMIT,
            knowledge_library=knowledge_library,
            knowledge_context_limit=settings.MEMORY_CONTEXT_LIMIT,
            knowledge_context_enabled=(
                provider == "ollama"
                or local_voice_required
                or settings.KNOWLEDGE_ALLOW_CLOUD
            ),
        )

        if input_mode == "console":
            run_conversation(agent, speech)
        elif input_mode == "wirepod":
            run_voice_conversation(
                agent,
                speech,
                WirePodTranscriptListener(settings.WIREPOD_HOST),
                listen_timeout=settings.VOICE_LISTEN_TIMEOUT,
            )
        else:
            print("INPUT_MODE must be either 'console' or 'wirepod'.")


if __name__ == "__main__":
    main()
