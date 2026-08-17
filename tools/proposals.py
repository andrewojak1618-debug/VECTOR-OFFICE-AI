"""Review untrusted model tool proposals without granting authority."""

import json
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType

from tools.permissions import PermissionLevel
from tools.registry import (
    ToolArguments,
    ToolRegistry,
    ToolValue,
)
from tools.tool_values import TOOL_NAME_PATTERN


PROPOSAL_SCHEMA_VERSION = 1
MAX_PROPOSAL_RESPONSE_CHARS = 2_048


class ToolProposalStatus(Enum):
    """Classify one untrusted structured model response."""

    NO_PROPOSAL = "no_proposal"
    PROPOSED = "proposed"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ToolProposalOption:
    """Map one model-visible identifier to a fixed local tool call."""

    proposal_id: str
    tool_name: str
    label: str
    arguments: tuple[tuple[str, ToolValue], ...] = ()

    def __post_init__(self) -> None:
        if TOOL_NAME_PATTERN.fullmatch(self.proposal_id) is None:
            raise ValueError("Proposal identifier must use safe characters.")
        if TOOL_NAME_PATTERN.fullmatch(self.tool_name) is None:
            raise ValueError("Proposal tool name must use safe characters.")
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("Proposal label must not be empty.")
        names = tuple(name for name, _value in self.arguments)
        if len(names) != len(set(names)):
            raise ValueError("Proposal argument names must be unique.")


@dataclass(frozen=True)
class ToolProposal:
    """Carry one locally mapped suggestion without an authorization object."""

    proposal_id: str
    tool_name: str
    label: str
    permission: PermissionLevel
    arguments: ToolArguments = field(
        default_factory=lambda: MappingProxyType({}),
    )


@dataclass(frozen=True)
class ToolProposalReview:
    """Return a proposal decision without retaining raw model output."""

    status: ToolProposalStatus
    proposal: ToolProposal | None = None
    error_code: str | None = None

    @property
    def accepted(self) -> bool:
        """Report whether a safe local proposal was produced."""
        return self.status is ToolProposalStatus.PROPOSED


SAFE_VECTOR_PROPOSAL_OPTIONS = (
    ToolProposalOption(
        "vector.list_actions",
        "vector.list_actions",
        "sichere Aktionen anzeigen",
    ),
    ToolProposalOption(
        "vector.head_up",
        "vector.perform_action",
        "Kopf nach oben",
        (("action", "head_up"),),
    ),
    ToolProposalOption(
        "vector.head_level",
        "vector.perform_action",
        "Kopf gerade",
        (("action", "head_level"),),
    ),
    ToolProposalOption(
        "vector.lift_up",
        "vector.perform_action",
        "Lift anheben",
        (("action", "lift_up"),),
    ),
    ToolProposalOption(
        "vector.lift_down",
        "vector.perform_action",
        "Lift absenken",
        (("action", "lift_down"),),
    ),
    ToolProposalOption(
        "vector.greeting",
        "vector.perform_action",
        "Begrüßungsanimation",
        (("action", "greeting"),),
    ),
    ToolProposalOption(
        "vector.eyes_only",
        "vector.perform_action",
        "Augenanimation",
        (("action", "eyes_only"),),
    ),
)


class ToolProposalReviewer:
    """Accept only fixed options that still satisfy the local registry."""

    def __init__(
        self,
        registry: ToolRegistry,
        options: tuple[ToolProposalOption, ...] = SAFE_VECTOR_PROPOSAL_OPTIONS,
    ):
        if not isinstance(registry, ToolRegistry):
            raise TypeError("Tool proposal reviewer requires a ToolRegistry.")
        self.registry = registry
        self._options = self._index_options(options)

    def catalog(self) -> tuple[ToolProposalOption, ...]:
        """Return only options currently safe to expose to a model."""
        return tuple(
            option
            for option in self._options.values()
            if self._inspect_option(option) is not None
        )

    def review(self, model_output: str) -> ToolProposalReview:
        """Parse and validate one strict JSON proposal without execution."""
        payload = _decode_payload(model_output)
        if payload is None:
            return _rejected("invalid_proposal_json")
        if set(payload) != {"schema_version", "proposal_id"}:
            return _rejected("invalid_proposal_schema")
        if type(payload["schema_version"]) is not int:
            return _rejected("invalid_proposal_version")
        if payload["schema_version"] != PROPOSAL_SCHEMA_VERSION:
            return _rejected("unsupported_proposal_version")
        proposal_id = payload["proposal_id"]
        if proposal_id is None:
            return ToolProposalReview(ToolProposalStatus.NO_PROPOSAL)
        if not isinstance(proposal_id, str):
            return _rejected("invalid_proposal_id")
        option = self._options.get(proposal_id)
        if option is None:
            return _rejected("proposal_not_allowed")
        proposal = self._inspect_option(option)
        if proposal is None:
            return _rejected("proposal_target_unavailable")
        return ToolProposalReview(ToolProposalStatus.PROPOSED, proposal)

    def _inspect_option(self, option: ToolProposalOption) -> ToolProposal | None:
        arguments = MappingProxyType(dict(option.arguments))
        inspection = self.registry.inspect_call(option.tool_name, arguments)
        definition = inspection.definition
        if not inspection.valid or definition is None:
            return None
        if definition.permission is PermissionLevel.DANGEROUS:
            return None
        if any(parameter.sensitive for parameter in definition.parameters):
            return None
        return ToolProposal(
            option.proposal_id,
            option.tool_name,
            option.label,
            definition.permission,
            inspection.arguments,
        )

    @staticmethod
    def _index_options(
        options: tuple[ToolProposalOption, ...],
    ) -> dict[str, ToolProposalOption]:
        indexed = {}
        for option in options:
            if not isinstance(option, ToolProposalOption):
                raise TypeError("Proposal options must be ToolProposalOption values.")
            if option.proposal_id in indexed:
                raise ValueError("Proposal identifiers must be unique.")
            indexed[option.proposal_id] = option
        return indexed


class _DuplicateKeyError(ValueError):
    pass


def _decode_payload(model_output: str) -> dict | None:
    if not isinstance(model_output, str):
        return None
    if not model_output.strip() or len(model_output) > MAX_PROPOSAL_RESPONSE_CHARS:
        return None
    try:
        payload = json.loads(model_output, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, _DuplicateKeyError):
        return None
    return payload if isinstance(payload, dict) else None


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError
        result[key] = value
    return result


def _rejected(error_code: str) -> ToolProposalReview:
    return ToolProposalReview(ToolProposalStatus.REJECTED, error_code=error_code)
