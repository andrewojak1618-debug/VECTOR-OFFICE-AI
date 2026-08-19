"""Read and validate bounded values from the process environment."""

import os


def get_int_setting(
    name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    """Read one bounded integer setting or return its default."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return value


def get_bool_setting(name: str, default: bool) -> bool:
    """Read one strict boolean setting or return its default."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    normalized_value = raw_value.strip().casefold()
    if normalized_value in {"1", "true", "yes", "on"}:
        return True
    if normalized_value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(
        f"{name} must be true/false, yes/no, on/off, or 1/0."
    )


def get_float_setting(
    name: str,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    """Read one bounded floating-point setting or return its default."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number.") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return value
