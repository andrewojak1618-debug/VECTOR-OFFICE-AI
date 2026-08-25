"""Executable entry point for Vector Office AI Core."""

from application.conversation import (
    respond_and_speak,
    run_conversation,
    run_voice_conversation,
)
from application.runtime import run_application
from config.settings import settings


def main() -> None:
    """Startet die Anwendung und signalisiert Startblockaden an den Watchdog."""
    if not run_application(settings):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
