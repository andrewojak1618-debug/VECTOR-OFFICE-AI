import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def get_int_setting(
    name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc

    if not minimum <= value <= maximum:
        raise ValueError(
            f"{name} must be between {minimum} and {maximum}."
        )

    return value


class Settings:
    APP_NAME = "Vector Office AI"
    VERSION = "0.1.0"

    VECTOR_NAME = os.getenv("VECTOR_NAME", "Vector")

    WIREPOD_HOST = os.getenv(
        "WIREPOD_HOST",
        "http://127.0.0.1:8080",
    )

    VECTOR_SERIAL = os.getenv("VECTOR_SERIAL", "")

    TTS_VOICE = os.getenv(
        "TTS_VOICE",
        "Microsoft Stefan",
    )

    TTS_VOLUME = get_int_setting(
        "TTS_VOLUME",
        default=50,
        minimum=0,
        maximum=100,
    )

settings = Settings()

