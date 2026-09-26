"""Form-side validation, derived from the spec.

The form calls its command's function directly rather than routing values
through the CLI's parser, so the checks a CLI would have performed have to
happen here. This module is pure -- no NiceGUI, no framework imports -- so the
whole error table is unit-testable on its own.
"""

from __future__ import annotations

import enum
from collections.abc import Iterable, Mapping
from typing import Any

from .spec import MISSING, ParamSpec

REQUIRED = "This field is required"
NOT_A_NUMBER = "Must be a number"
NOT_AN_INTEGER = "Must be a whole number"


def collect_errors(
    params: Iterable[ParamSpec], values: Mapping[tuple[str, ...], Any]
) -> dict[tuple[str, ...], str]:
    """Validate widget values against their specs, keyed by parameter path."""
    errors: dict[tuple[str, ...], str] = {}
    for param in params:
        error = check(param, values.get(param.path, MISSING))
        if error is not None:
            errors[param.path] = error
    return errors


def check(param: ParamSpec, value: Any) -> str | None:
    """The first validation failure for one parameter, or ``None``."""
    if param.is_flag or param.type is bool:
        return None  # an unchecked box is a valid False

    if param.multiple:
        items = list(value) if isinstance(value, (list, tuple, set, frozenset)) else []
        if not items:
            return REQUIRED if param.required else None
        return next((e for e in (_check_scalar(param, i) for i in items) if e), None)

    if _is_empty(value):
        return REQUIRED if param.required else None
    return _check_scalar(param, value)


def _is_empty(value: Any) -> bool:
    return value is None or value is MISSING or (isinstance(value, str) and not value.strip())


def _check_scalar(param: ParamSpec, value: Any) -> str | None:
    if param.choices is not None and not _in_choices(param, value):
        return f"Must be one of: {', '.join(param.choices)}"

    if param.type in (int, float):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return NOT_A_NUMBER
        if param.type is int and not number.is_integer():
            return NOT_AN_INTEGER
        if param.minimum is not None and number < param.minimum:
            return f"Must be at least {_trim(param.minimum)}"
        if param.maximum is not None and number > param.maximum:
            return f"Must be at most {_trim(param.maximum)}"
    return None


def _in_choices(param: ParamSpec, value: Any) -> bool:
    if isinstance(value, enum.Enum):
        value = value.value if isinstance(value.value, str) else value.name
    return str(value) in (param.choices or ())


def _trim(number: float) -> str:
    return str(int(number)) if float(number).is_integer() else str(number)
