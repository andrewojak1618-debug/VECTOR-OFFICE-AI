"""Provide bounded local fallback behavior for language-model outages."""

from collections.abc import Sequence
from enum import Enum

from brain.agent import LanguageModel
from brain.context import ChatMessage
from brain.provider_diagnostics import emit_provider
from diagnostics.events import DiagnosticLevel, StructuredDiagnosticReporter


class ProviderNotice(Enum):
    """Describe one consumable provider transition without response content."""

    LOCAL_FALLBACK = "local_fallback"
    ALL_UNAVAILABLE = "all_unavailable"


class FallbackProvider:
    """Use a secondary model only when the primary model is unavailable."""

    def __init__(
        self,
        primary: LanguageModel,
        fallback: LanguageModel,
        diagnostics: StructuredDiagnosticReporter | None = None,
    ):
        """Initialisiert Primärmodell, lokalen Rückfall und optionale Diagnose."""
        self.primary = primary
        self.fallback = fallback
        self.diagnostics = diagnostics
        self._primary_unavailable = False
        self._pending_notice: ProviderNotice | None = None

    def generate(self, messages: Sequence[ChatMessage]) -> str:
        """Liefert die Primärantwort oder nutzt bewusst das lokale Rückfallmodell."""
        content = self._try_primary(messages)
        if content:
            return content
        print("OpenAI unavailable. Using local Ollama fallback.")
        emit_provider(
            self.diagnostics,
            DiagnosticLevel.WARNING,
            "provider",
            "fallback.activated",
            provider="openai",
            fallback="ollama",
            reason_code="primary-unavailable",
        )
        return self._generate_fallback(messages)

    def _try_primary(self, messages: Sequence[ChatMessage]) -> str:
        """Versucht das Primärmodell und merkt dessen Ausfall ohne Inhaltsprotokoll."""
        try:
            content = self.primary.generate(messages).strip()
        except RuntimeError:
            self._mark_primary_unavailable()
            return ""
        if not content:
            self._mark_primary_unavailable()
            return ""
        self._primary_unavailable = False
        self._pending_notice = None
        return content

    def _generate_fallback(self, messages: Sequence[ChatMessage]) -> str:
        """Erzeugt lokal eine Antwort und unterscheidet einen vollständigen Ausfall."""
        try:
            content = self.fallback.generate(messages)
        except RuntimeError:
            if self._pending_notice is not None:
                self._pending_notice = ProviderNotice.ALL_UNAVAILABLE
            raise RuntimeError(
                "OpenAI and the local Ollama fallback both failed."
            ) from None
        if self._pending_notice is not None:
            self._pending_notice = ProviderNotice.LOCAL_FALLBACK
        return content

    def consume_notice(self) -> ProviderNotice | None:
        """Liefert einen Ausfallhinweis einmalig und löscht seinen offenen Zustand."""
        notice = self._pending_notice
        self._pending_notice = None
        return notice

    def _mark_primary_unavailable(self) -> None:
        """Markiert den ersten Primärausfall für eine einmalige Sprachausgabe."""
        if not self._primary_unavailable:
            self._pending_notice = ProviderNotice.ALL_UNAVAILABLE
        self._primary_unavailable = True
