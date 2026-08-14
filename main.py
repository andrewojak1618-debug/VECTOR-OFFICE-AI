from config.settings import settings
from vector.client import VectorClient
from vector.sdk_client import VectorSDKClient


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
        print("WirePod is not reachable. ❌")
        return

    print("WirePod is online. ✅")

    print()
    print("Starting Vector SDK test...")

    vector = VectorSDKClient(settings.VECTOR_SERIAL)

    if vector.test_connection():
        print()
        print("Testing direct speech...")

        vector.say(
            "Hallo. Vector Office AI Core ist jetzt mit mir verbunden."
        )


if __name__ == "__main__":
    main()