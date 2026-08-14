"""Explicit permission decisions for controlled Vector tool execution."""

from dataclasses import dataclass
from enum import Enum


class PermissionLevel(Enum):
    """Classify a tool by the strongest effect it may produce."""

    READ_ONLY = "read_only"
    MUTATING = "mutating"
    DANGEROUS = "dangerous"


@dataclass(frozen=True)
class ToolAuthorization:
    """Carry explicit user authority for one registry invocation."""

    allow_mutation: bool = False
    confirmed: bool = False

    def __post_init__(self) -> None:
        if type(self.allow_mutation) is not bool or type(self.confirmed) is not bool:
            raise TypeError("Tool authorization flags must be boolean.")


@dataclass(frozen=True)
class PermissionDecision:
    """Describe an allow or deny decision without sensitive arguments."""

    allowed: bool
    code: str
    message: str


class ToolPermissionPolicy:
    """Apply deny-by-default rules to tool permission levels."""

    def decide(
        self,
        level: PermissionLevel,
        authorization: ToolAuthorization | None = None,
    ) -> PermissionDecision:
        """Return the deterministic permission decision for one invocation."""
        invalid = self._invalid_request(level, authorization)
        if invalid is not None:
            return invalid
        authority = authorization or ToolAuthorization()
        if level is PermissionLevel.READ_ONLY:
            return PermissionDecision(True, "allowed", "Read-only tool allowed.")
        if not authority.allow_mutation:
            return PermissionDecision(
                False,
                "mutation_not_allowed",
                "Mutating tools require explicit user authorization.",
            )
        if level is PermissionLevel.DANGEROUS and not authority.confirmed:
            return PermissionDecision(
                False,
                "confirmation_required",
                "Dangerous tools require explicit per-call confirmation.",
            )
        return PermissionDecision(True, "allowed", "Authorized tool allowed.")

    @staticmethod
    def _invalid_request(
        level: object,
        authorization: object,
    ) -> PermissionDecision | None:
        if not isinstance(level, PermissionLevel):
            return PermissionDecision(
                False,
                "invalid_permission",
                "Tool permission is invalid.",
            )
        if authorization is not None and not isinstance(
            authorization,
            ToolAuthorization,
        ):
            return PermissionDecision(
                False,
                "invalid_authorization",
                "Tool authorization is invalid.",
            )
        return None
