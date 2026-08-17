"""Define and validate flat values shared by controlled tool calls."""

import math
import re
from collections.abc import Mapping
from enum import Enum
from types import MappingProxyType
from typing import TypeAlias


ToolValue: TypeAlias = str | int | float | bool | None
ToolArguments: TypeAlias = Mapping[str, ToolValue]
ToolOutput: TypeAlias = Mapping[str, ToolValue]
TOOL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")


class ToolParameterType(Enum):
    """Define the supported flat parameter types for tool calls."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"


def validate_identifier(value: str, label: str) -> None:
    """Require one lowercase identifier that is safe for local lookup."""
    if not isinstance(value, str) or TOOL_NAME_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{label} name must use lowercase safe characters.")


def safe_requested_name(value: object) -> str | None:
    """Return a syntactically safe requested name or no name."""
    if isinstance(value, str) and TOOL_NAME_PATTERN.fullmatch(value) is not None:
        return value
    return None


def normalize_output(output: ToolOutput) -> ToolOutput:
    """Freeze one finite, flat tool output mapping."""
    if not isinstance(output, Mapping):
        raise TypeError("Tool output must be a mapping.")
    if not all(
        isinstance(key, str) and is_tool_value(value)
        for key, value in output.items()
    ):
        raise TypeError("Tool output must contain flat structured values.")
    return MappingProxyType(dict(output))


def is_tool_value(value: object) -> bool:
    """Report whether a value is flat and safe for structured tool data."""
    if type(value) is float:
        return math.isfinite(value)
    return value is None or type(value) in (str, int, bool)


def matches_type(value: ToolValue, parameter_type: ToolParameterType) -> bool:
    """Match one flat value against its declared parameter type."""
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
