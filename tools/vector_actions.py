"""Expose allowlisted Vector behavior through the central tool registry."""

from dataclasses import dataclass

from tools.permissions import PermissionLevel
from tools.registry import (
    ToolArguments,
    ToolDefinition,
    ToolOutput,
    ToolParameter,
    ToolParameterType,
    ToolRegistry,
)
from vector.actions import VectorActions


@dataclass(frozen=True)
class VectorActionTool:
    """Execute one fixed action alias through the protected Vector boundary."""

    actions: VectorActions

    @property
    def definition(self) -> ToolDefinition:
        """Beschreibt das verändernde Aktions-Tool mit fester Allowlist."""
        allowed = ", ".join(self.actions.available_actions())
        return ToolDefinition(
            name="vector.perform_action",
            description=f"Perform one allowlisted Vector action: {allowed}.",
            permission=PermissionLevel.MUTATING,
            parameters=(ToolParameter(
                "action",
                "Exact allowlisted Vector action name.",
                ToolParameterType.STRING,
            ),),
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Führt eine validierte Aktion aus oder scheitert sicher an der Registrygrenze."""
        action = str(arguments["action"])
        if not self.actions.perform(action):
            raise RuntimeError("Vector action did not complete.")
        return {"action": action, "completed": True}


@dataclass(frozen=True)
class VectorEmergencyStopTool:
    """Expose the latched motor stop as an explicit mutating tool."""

    actions: VectorActions

    @property
    def definition(self) -> ToolDefinition:
        """Beschreibt den Notfallstopp ohne akzeptierte Parameter."""
        return ToolDefinition(
            name="vector.emergency_stop",
            description="Cancel active Vector behavior and stop every motor.",
            permission=PermissionLevel.MUTATING,
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Verriegelt den Notfallstopp und liefert ein strukturiertes Ergebnis."""
        if not self.actions.emergency_stop():
            raise RuntimeError("Vector emergency stop could not be confirmed.")
        return {"stopped": True, "latched": True}


@dataclass(frozen=True)
class VectorActionListTool:
    """Expose the fixed action names without touching the physical robot."""

    actions: VectorActions

    @property
    def definition(self) -> ToolDefinition:
        """Beschreibt das rein lesende Tool zur Anzeige der Aktions-Allowlist."""
        return ToolDefinition(
            name="vector.list_actions",
            description="List the fixed safe Vector action aliases.",
            permission=PermissionLevel.READ_ONLY,
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Liefert sichere Aktionsnamen als flachen strukturierten Registrywert."""
        names = ", ".join(self.actions.available_actions())
        return {"actions": names, "count": len(self.actions.available_actions())}


def register_vector_action_tools(
    registry: ToolRegistry,
    actions: VectorActions,
) -> None:
    """Registriert ausschließlich kontrollierte Aktionen und den Notfallstopp."""
    registry.register(VectorActionListTool(actions))
    registry.register(VectorActionTool(actions))
    registry.register(VectorEmergencyStopTool(actions))
