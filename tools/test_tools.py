"""Side-effect-free diagnostic tools for registry integration tests."""

from dataclasses import dataclass

from tools.permissions import PermissionLevel
from tools.registry import (
    ToolArguments,
    ToolDefinition,
    ToolOutput,
    ToolParameter,
    ToolParameterType,
)


@dataclass(frozen=True)
class EchoTestTool:
    """Echo public test text while deliberately ignoring a secret argument."""

    @property
    def definition(self) -> ToolDefinition:
        """Describe the side-effect-free diagnostic parameters."""
        return ToolDefinition(
            name="test.echo",
            description="Return supplied test text without external effects.",
            permission=PermissionLevel.READ_ONLY,
            parameters=(
                ToolParameter(
                    "text",
                    "Public diagnostic text to return.",
                    ToolParameterType.STRING,
                ),
                ToolParameter(
                    "secret",
                    "Optional sensitive value used only to verify redaction.",
                    ToolParameterType.STRING,
                    required=False,
                    sensitive=True,
                ),
            ),
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Return only the non-sensitive diagnostic text."""
        return {"echo": arguments["text"]}
