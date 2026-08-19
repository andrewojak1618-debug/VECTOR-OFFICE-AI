"""Emit content-free diagnostic metadata for language-model providers."""

from diagnostics.events import DiagnosticLevel, StructuredDiagnosticReporter


def emit_provider(
    diagnostics: StructuredDiagnosticReporter | None,
    level: DiagnosticLevel,
    component: str,
    code: str,
    **details: bool | float | int | str | None,
) -> None:
    """Emit validated provider metadata when diagnostics are enabled."""
    if diagnostics is not None:
        diagnostics.emit(level, component, code, **details)
