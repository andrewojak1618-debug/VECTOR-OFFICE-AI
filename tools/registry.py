"""Central registration, validation, auditing, and execution of safe tools."""

import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Protocol, TypeAlias

from tools.permissions import (
    PermissionDecision,
    PermissionLevel,
    ToolAuthorization,
    ToolPermissionPolicy,
)


ToolValue: TypeAlias = str | int | float | bool | None
ToolArguments: TypeAlias = Mapping[str, ToolValue]
ToolOutput: TypeAlias = Mapping[str, ToolValue]
AuditSink: TypeAlias = Callable[["ToolAuditEvent"], None]
TOOL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")
REDACTED_ARGUMENT = "[REDACTED]"


class ToolParameterType(Enum):
    """Define the supported flat parameter types for tool calls."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"


class ToolResultStatus(Enum):
    """Classify a structured registry execution result."""

    SUCCESS = "success"
    BLOCKED = "blocked"
    INVALID = "invalid"
    FAILED = "failed"


@dataclass(frozen=True)
class ToolParameter:
    """Describe one accepted tool argument and its privacy treatment."""

    name: str
    description: str
    parameter_type: ToolParameterType
    required: bool = True
    sensitive: bool = False

    def __post_init__(self) -> None:
        _validate_identifier(self.name, "Tool parameter")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("Tool parameter description must not be empty.")
        if not isinstance(self.parameter_type, ToolParameterType):
            raise TypeError("Tool parameter type must be a ToolParameterType.")
        if type(self.required) is not bool or type(self.sensitive) is not bool:
            raise TypeError("Tool parameter flags must be boolean.")


@dataclass(frozen=True)
class ToolDefinition:
    """Declare one registered tool without embedding executable behavior."""

    name: str
    description: str
    permission: PermissionLevel
    parameters: tuple[ToolParameter, ...] = ()

    def __post_init__(self) -> None:
        _validate_identifier(self.name, "Tool")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("Tool description must not be empty.")
        if not isinstance(self.permission, PermissionLevel):
            raise TypeError("Tool permission must be a PermissionLevel.")
        object.__setattr__(self, "parameters", tuple(self.parameters))
        names = tuple(parameter.name for parameter in self.parameters)
        if not all(isinstance(item, ToolParameter) for item in self.parameters):
            raise TypeError("Tool parameters must be ToolParameter values.")
        if len(names) != len(set(names)):
            raise ValueError("Tool parameter names must be unique.")


@dataclass(frozen=True)
class ToolExecutionResult:
    """Return a structured success or safe failure to the agent layer."""

    tool_name: str
    status: ToolResultStatus
    message: str
    output: ToolOutput = field(default_factory=lambda: MappingProxyType({}))
    error_code: str | None = None

    @property
    def succeeded(self) -> bool:
        """Report whether the tool completed successfully."""
        return self.status is ToolResultStatus.SUCCESS


@dataclass(frozen=True)
class ToolAuditEvent:
    """Expose a sanitized execution event for optional local auditing."""

    tool_name: str
    permission: PermissionLevel | None
    arguments: ToolArguments
    status: ToolResultStatus
    error_code: str | None


class Tool(Protocol):
    """Provide metadata and side-effect behavior behind one uniform boundary."""

    @property
    def definition(self) -> ToolDefinition:
        """Return immutable metadata used for validation and authorization."""
        ...

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Execute validated arguments and return structured output fields."""
        ...


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
        self.policy = policy or ToolPermissionPolicy()
        self.audit_sink = audit_sink
        self._tools: dict[str, _RegisteredTool] = {}

    def register(self, tool: Tool) -> None:
        """Register one unique, fully described tool."""
        definition = tool.definition
        if not isinstance(definition, ToolDefinition):
            raise TypeError("Tool definition must be a ToolDefinition.")
        name = definition.name
        if name in self._tools:
            raise ValueError(f"Tool is already registered: {name}")
        self._tools[name] = _RegisteredTool(definition, tool)

    def definitions(self) -> tuple[ToolDefinition, ...]:
        """Return registered definitions in deterministic name order."""
        return tuple(
            self._tools[name].definition
            for name in sorted(self._tools)
        )

    def execute(
        self,
        tool_name: str,
        arguments: ToolArguments,
        authorization: ToolAuthorization | None = None,
    ) -> ToolExecutionResult:
        """Validate, authorize, execute, and audit one requested tool."""
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
        if self.audit_sink is not None:
            self._emit_audit(ToolAuditEvent(
                tool_name,
                None,
                MappingProxyType({}),
                result.status,
                result.error_code,
            ))

    def _emit_audit(self, event: ToolAuditEvent) -> None:
        try:
            self.audit_sink(event)
        except Exception:
            return

    @staticmethod
    def _blocked(tool_name: str, code: str) -> ToolExecutionResult:
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
        return ToolExecutionResult(
            tool_name,
            ToolResultStatus.BLOCKED,
            decision.message,
            error_code=decision.code,
        )

    @staticmethod
    def _invalid(tool_name: str, code: str) -> ToolExecutionResult:
        return ToolExecutionResult(
            tool_name,
            ToolResultStatus.INVALID,
            "Tool arguments are invalid.",
            error_code=code,
        )

    @staticmethod
    def _failed(tool_name: str, code: str) -> ToolExecutionResult:
        return ToolExecutionResult(
            tool_name,
            ToolResultStatus.FAILED,
            "Tool execution failed.",
            error_code=code,
        )


def _validate_identifier(value: str, label: str) -> None:
    if not isinstance(value, str) or TOOL_NAME_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{label} name must use lowercase safe characters.")


def _safe_requested_name(value: object) -> str | None:
    if isinstance(value, str) and TOOL_NAME_PATTERN.fullmatch(value) is not None:
        return value
    return None


def _normalize_output(output: ToolOutput) -> ToolOutput:
    if not isinstance(output, Mapping):
        raise TypeError("Tool output must be a mapping.")
    if not all(
        isinstance(key, str) and _is_tool_value(value)
        for key, value in output.items()
    ):
        raise TypeError("Tool output must contain flat structured values.")
    return MappingProxyType(dict(output))


def _is_tool_value(value: object) -> bool:
    if type(value) is float:
        return math.isfinite(value)
    return value is None or type(value) in (str, int, bool)


def _matches_type(value: ToolValue, parameter_type: ToolParameterType) -> bool:
    if parameter_type is ToolParameterType.STRING:
        return type(value) is str
    if parameter_type is ToolParameterType.INTEGER:
        return type(value) is int
    if parameter_type is ToolParameterType.NUMBER:
        return type(value) is int or (
            type(value) is float and math.isfinite(value)
        )
    if parameter_type is ToolParameterType.BOOLEAN:
        return type(value) is bool
    return False
