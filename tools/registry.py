"""Central registration, validation, auditing, and execution of safe tools."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from tools.inspection import ToolCallInspection
from tools.permissions import (
    PermissionDecision,
    PermissionLevel,
    ToolAuthorization,
    ToolPermissionPolicy,
)
from tools.registry_types import (
    AuditSink,
    Tool,
    ToolAuditEvent,
    ToolDefinition,
    ToolExecutionResult,
    ToolParameter,
    ToolResultStatus,
)
from tools.tool_values import (
    ToolArguments,
    ToolOutput,
    ToolParameterType,
    ToolValue,
    matches_type as _matches_type,
    normalize_output as _normalize_output,
    safe_requested_name as _safe_requested_name,
)


REDACTED_ARGUMENT = "[REDACTED]"


@dataclass(frozen=True)
class _RegisteredTool:
    definition: ToolDefinition
    implementation: Tool


class ToolRegistry:
    """Deny unknown tools and mediate every registered tool invocation."""

    def __init__(
        self,
        policy: ToolPermissionPolicy | None = None,
        audit_sink: AuditSink | None = None,
    ):
        """Initialisiert eine leere Registry mit Berechtigungs- und optionalem Auditsink."""
        self.policy = policy or ToolPermissionPolicy()
        self.audit_sink = audit_sink
        self._tools: dict[str, _RegisteredTool] = {}

    def register(self, tool: Tool) -> None:
        """Registriert ein eindeutig benanntes und vollständig beschriebenes Tool."""
        definition = tool.definition
        if not isinstance(definition, ToolDefinition):
            raise TypeError("Tool definition must be a ToolDefinition.")
        name = definition.name
        if name in self._tools:
            raise ValueError(f"Tool is already registered: {name}")
        self._tools[name] = _RegisteredTool(definition, tool)

    def definitions(self) -> tuple[ToolDefinition, ...]:
        """Liefert registrierte Definitionen in deterministischer Namensreihenfolge."""
        return tuple(
            self._tools[name].definition
            for name in sorted(self._tools)
        )

    def inspect_call(
        self,
        tool_name: str,
        arguments: ToolArguments,
    ) -> ToolCallInspection:
        """Validiert einen vorgeschlagenen Aufruf ohne Berechtigungsprüfung oder Ausführung."""
        safe_name = _safe_requested_name(tool_name)
        if safe_name is None:
            return ToolCallInspection(
                "invalid-tool-name",
                error_code="tool_not_registered",
            )
        registered = self._tools.get(safe_name)
        if registered is None:
            return ToolCallInspection(safe_name, error_code="tool_not_registered")
        if not isinstance(arguments, Mapping):
            return ToolCallInspection(
                safe_name,
                registered.definition,
                error_code="invalid_arguments",
            )
        validated = self._validate_arguments(registered.definition, arguments)
        if isinstance(validated, ToolExecutionResult):
            return ToolCallInspection(
                safe_name,
                registered.definition,
                error_code=validated.error_code,
            )
        return ToolCallInspection(
            safe_name,
            registered.definition,
            MappingProxyType(validated),
        )

    def execute(
        self,
        tool_name: str,
        arguments: ToolArguments,
        authorization: ToolAuthorization | None = None,
    ) -> ToolExecutionResult:
        """Validiert, autorisiert, führt aus und auditiert ein angefordertes Tool."""
        safe_name = _safe_requested_name(tool_name)
        if safe_name is None:
            result = self._blocked("invalid-tool-name", "tool_not_registered")
            self._audit_unknown("invalid-tool-name", result)
            return result
        registered = self._tools.get(safe_name)
        if registered is None:
            result = self._blocked(safe_name, "tool_not_registered")
            self._audit_unknown(safe_name, result)
            return result
        if not isinstance(arguments, Mapping):
            result = self._invalid(safe_name, "invalid_arguments")
            self._audit(registered.definition, {}, result)
            return result
        definition = registered.definition
        validated = self._validate_arguments(definition, arguments)
        if isinstance(validated, ToolExecutionResult):
            self._audit(definition, arguments, validated)
            return validated
        decision = self.policy.decide(definition.permission, authorization)
        if not decision.allowed:
            result = self._permission_block(tool_name, decision)
            self._audit(definition, arguments, result)
            return result
        result = self._execute_tool(registered, validated)
        self._audit(definition, arguments, result)
        return result

    def _validate_arguments(
        self,
        definition: ToolDefinition,
        arguments: ToolArguments,
    ) -> dict[str, ToolValue] | ToolExecutionResult:
        """Prüft Argumentnamen, Pflichtwerte und Typen gegen die Tooldefinition."""
        expected = {parameter.name: parameter for parameter in definition.parameters}
        unknown = set(arguments) - set(expected)
        if unknown:
            return self._invalid(definition.name, "unknown_parameter")
        missing = {
            name for name, parameter in expected.items()
            if parameter.required and name not in arguments
        }
        if missing:
            return self._invalid(definition.name, "missing_parameter")
        if any(
            not _matches_type(arguments[name], parameter.parameter_type)
            for name, parameter in expected.items()
            if name in arguments
        ):
            return self._invalid(definition.name, "invalid_parameter_type")
        return dict(arguments)

    @staticmethod
    def _execute_tool(
        registered: _RegisteredTool,
        arguments: ToolArguments,
    ) -> ToolExecutionResult:
        """Führt die Implementierung aus und bereinigt Fehler sowie Ausgaben."""
        try:
            output = _normalize_output(registered.implementation.execute(arguments))
        except Exception:
            return ToolRegistry._failed(
                registered.definition.name,
                "tool_execution_failed",
            )
        return ToolExecutionResult(
            registered.definition.name,
            ToolResultStatus.SUCCESS,
            "Tool completed successfully.",
            output,
        )

    def _audit(
        self,
        definition: ToolDefinition,
        arguments: ToolArguments,
        result: ToolExecutionResult,
    ) -> None:
        """Übermittelt ein redigiertes Ereignis für einen bekannten Toolaufruf."""
        if self.audit_sink is None:
            return
        parameters = {item.name: item for item in definition.parameters}
        safe_arguments = {
            name: REDACTED_ARGUMENT if parameters[name].sensitive else value
            for name, value in arguments.items()
            if name in parameters
        }
        event = ToolAuditEvent(
            definition.name,
            definition.permission,
            MappingProxyType(safe_arguments),
            result.status,
            result.error_code,
        )
        self._emit_audit(event)

    def _audit_unknown(
        self,
        tool_name: str,
        result: ToolExecutionResult,
    ) -> None:
        """Auditiert einen unbekannten Toolnamen ohne übernommene Argumente."""
        if self.audit_sink is not None:
            self._emit_audit(ToolAuditEvent(
                tool_name,
                None,
                MappingProxyType({}),
                result.status,
                result.error_code,
            ))

    def _emit_audit(self, event: ToolAuditEvent) -> None:
        """Sendet ein Audit-Ereignis, ohne Auditsink-Fehler weiterzugeben."""
        try:
            self.audit_sink(event)
        except Exception:
            return

    @staticmethod
    def _blocked(tool_name: str, code: str) -> ToolExecutionResult:
        """Erzeugt ein strukturiertes blockiertes Toolergebnis."""
        return ToolExecutionResult(
            tool_name,
            ToolResultStatus.BLOCKED,
            "Tool execution was blocked.",
            error_code=code,
        )

    @staticmethod
    def _permission_block(
        tool_name: str,
        decision: PermissionDecision,
    ) -> ToolExecutionResult:
        """Überführt eine abgelehnte Berechtigungsentscheidung in ein Ergebnis."""
        return ToolExecutionResult(
            tool_name,
            ToolResultStatus.BLOCKED,
            decision.message,
            error_code=decision.code,
        )

    @staticmethod
    def _invalid(tool_name: str, code: str) -> ToolExecutionResult:
        """Erzeugt ein strukturiertes Ergebnis für ungültige Argumente."""
        return ToolExecutionResult(
            tool_name,
            ToolResultStatus.INVALID,
            "Tool arguments are invalid.",
            error_code=code,
        )

    @staticmethod
    def _failed(tool_name: str, code: str) -> ToolExecutionResult:
        """Erzeugt ein bereinigtes strukturiertes Ausführungsergebnis mit Fehler."""
        return ToolExecutionResult(
            tool_name,
            ToolResultStatus.FAILED,
            "Tool execution failed.",
            error_code=code,
        )
