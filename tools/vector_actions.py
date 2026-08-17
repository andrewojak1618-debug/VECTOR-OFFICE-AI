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
        """Describe the allowlisted mutating action tool."""
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
        """Run one validated action or fail safely at the registry boundary."""
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
        """Describe the emergency stop without accepting parameters."""
        return ToolDefinition(
            name="vector.emergency_stop",
            description="Cancel active Vector behavior and stop every motor.",
            permission=PermissionLevel.MUTATING,
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Latch the emergency stop and return a structured result."""
        if not self.actions.emergency_stop():
            raise RuntimeError("Vector emergency stop could not be confirmed.")
        return {"stopped": True, "latched": True}


@dataclass(frozen=True)
class VectorActionListTool:
    """Expose the fixed action names without touching the physical robot."""

    actions: VectorActions

    @property
    def definition(self) -> ToolDefinition:
        """Describe the read-only allowlist inspection tool."""
        return ToolDefinition(
            name="vector.list_actions",
            description="List the fixed safe Vector action aliases.",
            permission=PermissionLevel.READ_ONLY,
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Return safe aliases as a flat structured registry value."""
        names = ", ".join(self.actions.available_actions())
        return {"actions": names, "count": len(self.actions.available_actions())}


def register_vector_action_tools(
    registry: ToolRegistry,
    actions: VectorActions,
) -> None:
    """Register only the controlled action and emergency-stop tools."""
    registry.register(VectorActionListTool(actions))
    registry.register(VectorActionTool(actions))
    registry.register(VectorEmergencyStopTool(actions))
