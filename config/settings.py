"""Validated environment-based configuration for Vector Office AI."""

import os
from pathlib import Path

from dotenv import load_dotenv

from config.environment import (
    get_bool_setting,
    get_float_setting,
    get_int_setting,
)


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_EMBEDDING_PROVIDER = "ollama"
DEFAULT_KNOWLEDGE_ALLOW_CLOUD = False
DEFAULT_TOOL_AUDIT_ENABLED = True
DEFAULT_TOOL_AUDIT_RETENTION_DAYS = 30
DEFAULT_TOOL_AUDIT_MAX_ENTRIES = 1_000
DEFAULT_DIAGNOSTICS_ENABLED = True
DEFAULT_DIAGNOSTICS_MAX_BYTES = 1_000_000

load_dotenv(BASE_DIR / ".env", override=True)


class Settings:
    """Application settings loaded once from the local environment."""

    APP_NAME = "Vector Office AI"
    VERSION = "0.2.0-rc.1"

    VECTOR_NAME = os.getenv("VECTOR_NAME", "Vector")

    WIREPOD_HOST = os.getenv(
        "WIREPOD_HOST",
        "http://127.0.0.1:8080",
    )

    HOST_WATCHDOG_WIREPOD_EXECUTABLE = os.getenv(
        "HOST_WATCHDOG_WIREPOD_EXECUTABLE",
        str(
            Path(os.getenv("PROGRAMFILES", r"C:\Program Files"))
            / "wire-pod"
            / "chipper"
            / "chipper.exe"
        ),
    )

    HOST_WATCHDOG_POLL_INTERVAL = get_float_setting(
        "HOST_WATCHDOG_POLL_INTERVAL",
        default=0.5,
        minimum=0.25,
        maximum=30.0,
    )

    HOST_WATCHDOG_STARTUP_ATTEMPTS = get_int_setting(
        "HOST_WATCHDOG_STARTUP_ATTEMPTS",
        default=6,
        minimum=1,
        maximum=6,
    )

    HOST_WATCHDOG_APP_RESTART_ATTEMPTS = get_int_setting(
        "HOST_WATCHDOG_APP_RESTART_ATTEMPTS",
        default=3,
        minimum=0,
        maximum=4,
    )

    VECTOR_SERIAL = os.getenv("VECTOR_SERIAL", "")

    TTS_VOICE = os.getenv(
        "TTS_VOICE",
        "Microsoft Stefan",
    )

    TTS_PROVIDER = os.getenv("TTS_PROVIDER", "onecore")

    TTS_ALLOW_CLOUD = get_bool_setting(
        "TTS_ALLOW_CLOUD",
        default=False,
    )

    TTS_VOLUME = get_int_setting(
        "TTS_VOLUME",
        default=50,
        minimum=0,
        maximum=100,
    )

    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
    ELEVENLABS_MODEL = os.getenv(
        "ELEVENLABS_MODEL",
        "eleven_flash_v2_5",
    )
    ELEVENLABS_TIMEOUT = get_float_setting(
        "ELEVENLABS_TIMEOUT",
        default=15.0,
        minimum=1.0,
        maximum=60.0,
    )
    ELEVENLABS_STABILITY = get_float_setting(
        "ELEVENLABS_STABILITY",
        default=0.45,
        minimum=0.0,
        maximum=1.0,
    )
    ELEVENLABS_SIMILARITY = get_float_setting(
        "ELEVENLABS_SIMILARITY",
        default=0.75,
        minimum=0.0,
        maximum=1.0,
    )
    ELEVENLABS_STYLE = get_float_setting(
        "ELEVENLABS_STYLE",
        default=0.0,
        minimum=0.0,
        maximum=1.0,
    )
    ELEVENLABS_SPEED = get_float_setting(
        "ELEVENLABS_SPEED",
        default=1.02,
        minimum=0.7,
        maximum=1.2,
    )

    ROBOT_ACTION_TIMEOUT = get_int_setting(
        "ROBOT_ACTION_TIMEOUT",
        default=8,
        minimum=1,
        maximum=30,
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

    REFLECTION_ENABLED = get_bool_setting(
        "REFLECTION_ENABLED",
        default=True,
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

    OLLAMA_TEMPERATURE = get_float_setting(
        "OLLAMA_TEMPERATURE",
        default=0.25,
        minimum=0.0,
        maximum=2.0,
    )

    OLLAMA_MAX_OUTPUT_TOKENS = get_int_setting(
        "OLLAMA_MAX_OUTPUT_TOKENS",
        default=64,
        minimum=16,
        maximum=512,
    )

    OLLAMA_CONTEXT_WINDOW = get_int_setting(
        "OLLAMA_CONTEXT_WINDOW",
        default=4_096,
        minimum=1_024,
        maximum=32_768,
    )

    LLM_REQUEST_TIMEOUT = get_float_setting(
        "LLM_REQUEST_TIMEOUT",
        default=120.0,
        minimum=1.0,
        maximum=600.0,
    )

    LLM_MAX_ATTEMPTS = get_int_setting(
        "LLM_MAX_ATTEMPTS",
        default=2,
        minimum=1,
        maximum=5,
    )

    LLM_RETRY_DELAY = get_float_setting(
        "LLM_RETRY_DELAY",
        default=0.5,
        minimum=0.0,
        maximum=10.0,
    )

    OLLAMA_EXECUTABLE = os.getenv(
        "OLLAMA_EXECUTABLE",
        "",
    )

    EMBEDDING_PROVIDER = os.getenv(
        "EMBEDDING_PROVIDER",
        DEFAULT_EMBEDDING_PROVIDER,
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

    TOOL_AUDIT_ENABLED = get_bool_setting(
        "TOOL_AUDIT_ENABLED",
        default=DEFAULT_TOOL_AUDIT_ENABLED,
    )

    TOOL_AUDIT_RETENTION_DAYS = get_int_setting(
        "TOOL_AUDIT_RETENTION_DAYS",
        default=DEFAULT_TOOL_AUDIT_RETENTION_DAYS,
        minimum=1,
        maximum=3_650,
    )

    TOOL_AUDIT_MAX_ENTRIES = get_int_setting(
        "TOOL_AUDIT_MAX_ENTRIES",
        default=DEFAULT_TOOL_AUDIT_MAX_ENTRIES,
        minimum=1,
        maximum=100_000,
    )

    DIAGNOSTICS_ENABLED = get_bool_setting(
        "DIAGNOSTICS_ENABLED",
        default=DEFAULT_DIAGNOSTICS_ENABLED,
    )

    DIAGNOSTICS_PATH = Path(
        os.getenv(
            "DIAGNOSTICS_PATH",
            str(BASE_DIR / "data" / "diagnostics" / "events.jsonl"),
        )
    )

    DIAGNOSTICS_MAX_BYTES = get_int_setting(
        "DIAGNOSTICS_MAX_BYTES",
        default=DEFAULT_DIAGNOSTICS_MAX_BYTES,
        minimum=1_024,
        maximum=10_000_000,
    )

    KNOWLEDGE_ALLOW_CLOUD = get_bool_setting(
        "KNOWLEDGE_ALLOW_CLOUD",
        default=DEFAULT_KNOWLEDGE_ALLOW_CLOUD,
    )

    KNOWLEDGE_LEXICAL_WEIGHT = get_float_setting(
        "KNOWLEDGE_LEXICAL_WEIGHT",
        default=0.45,
        minimum=0.0,
        maximum=1.0,
    )

    KNOWLEDGE_SEMANTIC_WEIGHT = get_float_setting(
        "KNOWLEDGE_SEMANTIC_WEIGHT",
        default=0.55,
        minimum=0.0,
        maximum=1.0,
    )

    KNOWLEDGE_MIN_SIMILARITY = get_float_setting(
        "KNOWLEDGE_MIN_SIMILARITY",
        default=0.35,
        minimum=-1.0,
        maximum=1.0,
    )

settings = Settings()

