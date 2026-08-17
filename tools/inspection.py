"""Represent registry call validation without execution side effects."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.registry import ToolDefinition, ToolValue


@dataclass(frozen=True)
class ToolCallInspection:
    """Describe a registry-bound call without authorizing or executing it."""

    tool_name: str
    definition: ToolDefinition | None = None
    arguments: Mapping[str, ToolValue] = field(
        default_factory=lambda: MappingProxyType({}),
    )
    error_code: str | None = None

    @property
    def valid(self) -> bool:
        """Report whether name and arguments match the registered definition."""
        return self.definition is not None and self.error_code is None
