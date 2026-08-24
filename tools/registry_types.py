"""Definiert unveränderliche Typen und Verträge der Tool Registry."""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Protocol, TypeAlias

from tools.permissions import PermissionLevel
from tools.tool_values import (
    ToolArguments,
    ToolOutput,
    ToolParameterType,
    validate_identifier,
)


class ToolResultStatus(Enum):
    """Beschreibt den strukturierten Status einer Toolausführung."""

    SUCCESS = "success"
    BLOCKED = "blocked"
    INVALID = "invalid"
    FAILED = "failed"


@dataclass(frozen=True)
class ToolParameter:
    """Beschreibt ein erlaubtes Toolargument samt Datenschutzbehandlung."""

    name: str
    description: str
    parameter_type: ToolParameterType
    required: bool = True
    sensitive: bool = False

    def __post_init__(self) -> None:
        """Validiert Namen, Beschreibung, Parametertyp und Datenschutzmerkmale."""
        validate_identifier(self.name, "Tool parameter")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("Tool parameter description must not be empty.")
        if not isinstance(self.parameter_type, ToolParameterType):
            raise TypeError("Tool parameter type must be a ToolParameterType.")
        if type(self.required) is not bool or type(self.sensitive) is not bool:
            raise TypeError("Tool parameter flags must be boolean.")


@dataclass(frozen=True)
class ToolDefinition:
    """Beschreibt ein registriertes Tool ohne ausführbares Verhalten."""

    name: str
    description: str
    permission: PermissionLevel
    parameters: tuple[ToolParameter, ...] = ()

    def __post_init__(self) -> None:
        """Validiert Toolname, Berechtigung und eindeutige Parameterdefinitionen."""
        validate_identifier(self.name, "Tool")
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
    """Beschreibt Erfolg oder bereinigten Fehler für die Agentenschicht."""

    tool_name: str
    status: ToolResultStatus
    message: str
    output: ToolOutput = field(default_factory=lambda: MappingProxyType({}))
    error_code: str | None = None

    @property
    def succeeded(self) -> bool:
        """Meldet, ob das Tool erfolgreich abgeschlossen wurde."""
        return self.status is ToolResultStatus.SUCCESS


@dataclass(frozen=True)
class ToolAuditEvent:
    """Beschreibt ein bereinigtes Ereignis für die optionale lokale Prüfung."""

    tool_name: str
    permission: PermissionLevel | None
    arguments: ToolArguments
    status: ToolResultStatus
    error_code: str | None


class Tool(Protocol):
    """Beschreibt Metadaten und Verhalten hinter der einheitlichen Toolgrenze."""

    @property
    def definition(self) -> ToolDefinition:
        """Liefert unveränderliche Metadaten für Validierung und Autorisierung."""
        ...

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Führt validierte Argumente aus und liefert strukturierte Ausgabefelder."""
        ...


AuditSink: TypeAlias = Callable[[ToolAuditEvent], None]
