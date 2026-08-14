"""Validated environment-based configuration for Vector Office AI."""

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env", override=True)


def get_int_setting(
    name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    """Read one bounded integer setting or return its default."""
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


def get_bool_setting(name: str, default: bool) -> bool:
    """Read one strict boolean setting or return its default."""
    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    normalized_value = raw_value.strip().casefold()

    if normalized_value in {"1", "true", "yes", "on"}:
        return True

    if normalized_value in {"0", "false", "no", "off"}:
        return False

    raise ValueError(
        f"{name} must be true/false, yes/no, on/off, or 1/0."
    )


class Settings:
    """Application settings loaded once from the local environment."""

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

    INPUT_MODE = os.getenv(
        "INPUT_MODE",
        "console",
    )

    VOICE_LISTEN_TIMEOUT = get_int_setting(
        "VOICE_LISTEN_TIMEOUT",
        default=120,
        minimum=10,
        maximum=600,
    )

    VOICE_ALLOW_CLOUD = get_bool_setting(
        "VOICE_ALLOW_CLOUD",
        default=False,
    )

    LLM_PROVIDER = os.getenv(
        "LLM_PROVIDER",
        "openai",
    )

    LLM_FALLBACK_PROVIDER = os.getenv(
        "LLM_FALLBACK_PROVIDER",
        "ollama",
    )

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    OPENAI_MODEL = os.getenv(
        "OPENAI_MODEL",
        "gpt-5.6-luna",
    )

    OLLAMA_HOST = os.getenv(
        "OLLAMA_HOST",
        "http://127.0.0.1:11434",
    )

    OLLAMA_MODEL = os.getenv(
        "OLLAMA_MODEL",
        "llama3.2:3b",
    )

    OLLAMA_EXECUTABLE = os.getenv(
        "OLLAMA_EXECUTABLE",
        "",
    )

    EMBEDDING_PROVIDER = os.getenv(
        "EMBEDDING_PROVIDER",
        "ollama",
    )

    OLLAMA_EMBEDDING_MODEL = os.getenv(
        "OLLAMA_EMBEDDING_MODEL",
        "embeddinggemma",
    )

    OLLAMA_EMBEDDING_DIMENSION = get_int_setting(
        "OLLAMA_EMBEDDING_DIMENSION",
        default=0,
        minimum=0,
        maximum=65536,
    )

    OLLAMA_EMBEDDING_TIMEOUT = get_int_setting(
        "OLLAMA_EMBEDDING_TIMEOUT",
        default=60,
        minimum=1,
        maximum=600,
    )

    MEMORY_DB_PATH = Path(
        os.getenv(
            "MEMORY_DB_PATH",
            str(BASE_DIR / "data" / "vector_memory.db"),
        )
    )

    MEMORY_CONTEXT_LIMIT = get_int_setting(
        "MEMORY_CONTEXT_LIMIT",
        default=5,
        minimum=1,
        maximum=20,
    )

    KNOWLEDGE_ALLOW_CLOUD = get_bool_setting(
        "KNOWLEDGE_ALLOW_CLOUD",
        default=False,
    )

settings = Settings()

