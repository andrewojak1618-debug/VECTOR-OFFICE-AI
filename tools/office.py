"""Provide deterministic read-only office information through the registry."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from tools.permissions import PermissionLevel
from tools.registry import (
    ToolArguments,
    ToolDefinition,
    ToolOutput,
    ToolParameter,
    ToolParameterType,
    ToolRegistry,
)


DATE_MODE = "date"
TIME_MODE = "time"
ALLOWED_DATETIME_MODES = frozenset({DATE_MODE, TIME_MODE})
GERMAN_WEEKDAYS = (
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag",
)
GERMAN_MONTHS = (
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
)


def _local_now() -> datetime:
    return datetime.now().astimezone()


@dataclass(frozen=True)
class LocalDateTimeTool:
    """Return a locally generated German date or time without external access."""

    clock: Callable[[], datetime] = _local_now

    @property
    def definition(self) -> ToolDefinition:
        """Describe the fixed read-only date and time request."""
        return ToolDefinition(
            name="office.local_datetime",
            description="Return the local date or time in spoken German.",
            permission=PermissionLevel.READ_ONLY,
            parameters=(ToolParameter(
                "mode",
                "Exact local output mode: date or time.",
                ToolParameterType.STRING,
            ),),
        )

    def execute(self, arguments: ToolArguments) -> ToolOutput:
        """Create deterministic local metadata and one German spoken answer."""
        mode = str(arguments["mode"])
        if mode not in ALLOWED_DATETIME_MODES:
            raise ValueError("Unsupported local date and time mode.")
        current = self.clock()
        if not isinstance(current, datetime):
            raise TypeError("Local date and time clock must return datetime.")
        local = current.astimezone()
        spoken = _spoken_date(local) if mode == DATE_MODE else _spoken_time(local)
        return {
            "mode": mode,
            "date": local.date().isoformat(),
            "time": local.strftime("%H:%M"),
            "timezone": local.tzname() or "lokal",
            "spoken_text": spoken,
        }


def register_office_tools(
    registry: ToolRegistry,
    clock: Callable[[], datetime] | None = None,
) -> None:
    """Register fixed local office tools without network capabilities."""
    registry.register(LocalDateTimeTool(clock or _local_now))


def _spoken_date(value: datetime) -> str:
    weekday = GERMAN_WEEKDAYS[value.weekday()]
    month = GERMAN_MONTHS[value.month - 1]
    return f"Heute ist {weekday}, der {value.day}. {month} {value.year}."


def _spoken_time(value: datetime) -> str:
    if value.minute == 0:
        return f"Es ist {value.hour} Uhr."
    return f"Es ist {value.hour} Uhr {value.minute}."
