"""Steuert lokale Erinnerungsvorschläge und ihre getrennte Bestätigung."""

import re

from application.confirmation import ConfirmationDecision, classify_confirmation
from application.tool_conversation import ToolTurnResult, ToolTurnStatus
from brain.agent import Agent
from tools.memory_write import validate_memory_content
from tools.permissions import ToolAuthorization


MEMORY_TOOL_NAME = "memory.remember_confirmed"
MEMORY_PREFIX = re.compile(
    r"^(?:bitte\s+)?(?:merk(?:e|el)?\s+dir|merkt\s+ihr|jacke\s+dir|"
    r"erinnerung\s+speichern)\b",
    re.IGNORECASE,
)
MEMORY_CONFIRMATION = (
    "Soll ich diese Information als lokale Erinnerung speichern? "
    "Antworte mit Ja oder Nein."
)


class ControlledMemoryConversation:
    """Hält einen Sprachinhalt nur bis zur eindeutigen Einzelbestätigung."""

    def __init__(self, agent: Agent):
        """Initialisiert den Dialog ohne offenen Erinnerungsinhalt."""
        self.agent = agent
        self._pending_content: str | None = None

    @property
    def awaiting_confirmation(self) -> bool:
        """Meldet einen noch nicht bestätigten lokalen Erinnerungsvorschlag."""
        return self._pending_content is not None

    def cancel_pending(self) -> bool:
        """Verwirft einen offenen Inhalt vollständig aus dem Arbeitsspeicher."""
        existed = self._pending_content is not None
        self._pending_content = None
        return existed

    def handle(self, user_text: str) -> ToolTurnResult:
        """Erkennt einen expliziten Merksatz oder verarbeitet seine Bestätigung."""
        if self._pending_content is not None:
            return self._handle_confirmation(user_text)
        try:
            content = extract_memory_content(user_text)
        except ValueError:
            return ToolTurnResult(
                ToolTurnStatus.BLOCKED,
                "Die gewünschte Erinnerung ist leer oder zu lang.",
                True,
            )
        if content is None:
            return ToolTurnResult(ToolTurnStatus.NOT_HANDLED)
        self._pending_content = content
        return self._confirmation_result()

    def _handle_confirmation(self, user_text: str) -> ToolTurnResult:
        """Speichert nur nach Ja und verwirft bei Nein oder Abbruch den Inhalt."""
        decision = classify_confirmation(user_text)
        if decision in {ConfirmationDecision.REJECT, ConfirmationDecision.CANCEL}:
            self.cancel_pending()
            return ToolTurnResult(
                ToolTurnStatus.CANCELLED,
                "Die Erinnerung wurde nicht gespeichert.",
                True,
            )
        if decision is not ConfirmationDecision.CONFIRM:
            return self._confirmation_result()
        content = self._pending_content
        self._pending_content = None
        return self._store(content)

    def _store(self, content: str) -> ToolTurnResult:
        """Übergibt genau den bestätigten Inhalt einmalig an die Registry."""
        result = self.agent.execute_tool(
            MEMORY_TOOL_NAME,
            {"content": content},
            ToolAuthorization(allow_mutation=True, confirmed=True),
        )
        if not result.succeeded:
            return ToolTurnResult(
                ToolTurnStatus.FAILED,
                "Die Erinnerung konnte nicht lokal gespeichert werden.",
                True,
                result,
            )
        return ToolTurnResult(
            ToolTurnStatus.COMPLETED,
            str(result.output["spoken_text"]),
            True,
            result,
        )

    @staticmethod
    def _confirmation_result() -> ToolTurnResult:
        """Erzeugt die inhaltsfreie Frage für eine getrennte Ja-Nein-Antwort."""
        return ToolTurnResult(
            ToolTurnStatus.AWAITING_CONFIRMATION,
            MEMORY_CONFIRMATION,
            True,
        )


def extract_memory_content(user_text: str) -> str | None:
    """Extrahiert nur Inhalte hinter einem ausdrücklich gesprochenen Merkpräfix."""
    match = MEMORY_PREFIX.match(user_text.strip())
    if match is None:
        return None
    remainder = user_text.strip()[match.end():].strip()
    remainder = re.sub(r"^[,:]\s*", "", remainder)
    if remainder.casefold().startswith("dass "):
        remainder = remainder[5:]
    return validate_memory_content(remainder)
