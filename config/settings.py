import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


class Settings:
    APP_NAME = "Vector Office AI"
    VERSION = "0.1.0"

    VECTOR_NAME = os.getenv("VECTOR_NAME", "Vector")

    WIREPOD_HOST = os.getenv(
        "WIREPOD_HOST",
        "http://127.0.0.1:8080",
    )

    VECTOR_SERIAL = os.getenv("VECTOR_SERIAL", "")

settings = Settings()

