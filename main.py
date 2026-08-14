from brain.agent import Agent
from brain.providers import create_language_model
from config.settings import settings
from vector.client import VectorClient
from vector.sdk_client import VectorSDKClient
from vector.speech import VectorSpeech


def run_conversation(agent: Agent, speech: VectorSpeech) -> None:
    print()
    print("Conversation started.")
    print("Commands: /clear resets context, /exit ends the session.")

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
        agent = Agent(create_language_model(settings))
        run_conversation(agent, speech)


if __name__ == "__main__":
    main()
