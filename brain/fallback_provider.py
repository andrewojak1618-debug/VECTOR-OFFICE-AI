"""Provide bounded local fallback behavior for language-model outages."""

from collections.abc import Sequence
from enum import Enum

from brain.agent import LanguageModel
from brain.context import ChatMessage
from brain.provider_diagnostics import (
    ProviderErrorCode,
    ProviderEvent,
    emit_provider_event,
)
from diagnostics.events import StructuredDiagnosticReporter


class ProviderNotice(Enum):
    """Describe one consumable provider transition without response content."""

    LOCAL_FALLBACK = "local_fallback"
    ALL_UNAVAILABLE = "all_unavailable"
    PRIMARY_RECOVERED = "primary_recovered"


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
        self._response_source = "unspecified"

    @property
    def response_source(self) -> str:
        """Liefert die Herkunft der zuletzt erfolgreichen Modellantwort."""
        return self._response_source

    def generate(self, messages: Sequence[ChatMessage]) -> str:
        """Liefert die Primärantwort oder nutzt bewusst das lokale Rückfallmodell."""
        outage_started = not self._primary_unavailable
        content = self._try_primary(messages)
        if content:
            return content
        if not outage_started:
            return self._generate_fallback(messages)
        print("OpenAI unavailable. Using local Ollama fallback.")
        emit_provider_event(
            self.diagnostics,
            ProviderEvent.FALLBACK,
            "openai",
            fallback="ollama",
            error_code=ProviderErrorCode.PRIMARY_UNAVAILABLE,
        )
        return self._generate_fallback(messages)

    def _try_primary(self, messages: Sequence[ChatMessage]) -> str:
        """Versucht das Primärmodell und merkt dessen Ausfall ohne Inhaltsprotokoll."""
        was_unavailable = self._primary_unavailable
        try:
            result = self.primary.generate(messages)
        except RuntimeError:
            self._mark_primary_unavailable()
            return ""
        if not isinstance(result, str):
            self._mark_primary_unavailable()
            return ""
        content = result.strip()
        if not content:
            self._mark_primary_unavailable()
            return ""
        self._primary_unavailable = False
        if was_unavailable:
            self._pending_notice = ProviderNotice.PRIMARY_RECOVERED
            self._report_primary_recovery()
        else:
            self._pending_notice = None
        self._response_source = getattr(
            self.primary,
            "response_source",
            "primary",
        )
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
        self._response_source = getattr(
            self.fallback,
            "response_source",
            "fallback",
        )
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

    def _report_primary_recovery(self) -> None:
        """Meldet die Wiederherstellung des Primärproviders ohne Inhaltsdaten."""
        emit_provider_event(
            self.diagnostics,
            ProviderEvent.RECOVERED,
            "openai",
            fallback="ollama",
        )
