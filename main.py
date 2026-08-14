from brain.agent import Agent
from brain.providers import create_language_model
from config.settings import settings
from vector.client import VectorClient
from vector.sdk_client import VectorSDKClient
from vector.speech import VectorSpeech


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

        print()
        user_text = input("Du: ").strip()

        if not user_text:
            print("No question entered.")
            return

        print("Thinking...")

        try:
            answer = agent.respond(user_text)
        except (RuntimeError, ValueError) as exc:
            print(f"Brain request failed: {exc}")
            return

        print(f"Vector: {answer}")
        speech.say(answer)


if __name__ == "__main__":
    main()
