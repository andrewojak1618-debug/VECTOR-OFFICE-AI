"""Executable entry point for Vector Office AI Core."""

from application.conversation import (
    respond_and_speak,
    run_conversation,
    run_voice_conversation,
)
from application.runtime import run_application
from config.settings import settings


def main() -> None:
    """Run Vector Office AI Core with the local environment settings."""
    run_application(settings)


if __name__ == "__main__":
    main()
