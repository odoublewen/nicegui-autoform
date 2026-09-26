"""Conversion between Python values and the values NiceGUI elements hold.

A ``ui.number`` yields a float even for an int field, a ``ui.select`` yields the
choice string rather than the Enum member the callback wants, and a required
field starts out empty. These two functions are the only place that gap is
bridged.
"""

from __future__ import annotations

import enum
from pathlib import Path
from typing import Any

from .spec import MISSING, ParamSpec


def to_widget(param: ParamSpec, value: Any) -> Any:
    """Turn a Python value into something a NiceGUI element can hold."""
    if value is MISSING or value is None:
        return [] if param.multiple else (False if param.is_flag else None)
    if param.multiple:
        items = value if isinstance(value, (list, tuple, set, frozenset)) else [value]
        return [_scalar_to_widget(param, item) for item in items]
    return _scalar_to_widget(param, value)


def _scalar_to_widget(param: ParamSpec, value: Any) -> Any:
    if isinstance(value, enum.Enum):
        return value.value if isinstance(value.value, str) else value.name
    if isinstance(value, Path):
        return str(value)
    if param.is_flag or param.type is bool:
        return bool(value)
    if param.choices is not None:
        return str(value)
    return value


def from_widget(param: ParamSpec, value: Any) -> Any:
    """Turn a widget's value into what the command's callback expects.

    Returns :data:`MISSING` for an empty optional field, so that
    :meth:`~nicegui_autoform.spec.CommandSpec.bind` drops it and the callback's
    own default applies rather than being overwritten with ``None``.
    """
    if param.is_flag or param.type is bool:
        return bool(value)
    if param.multiple:
        items = value if isinstance(value, (list, tuple, set, frozenset)) else _split(value)
        converted = [_scalar_from_widget(param, item) for item in items if not _is_empty(item)]
        if not converted and not param.required:
            return param.default if param.has_default else MISSING
        return converted
    if _is_empty(value):
        return param.default if param.has_default else MISSING
    return _scalar_from_widget(param, value)


def _split(value: Any) -> list[Any]:
    """A free-text entry for a multi-value field splits on commas."""
    if _is_empty(value):
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _is_empty(value: Any) -> bool:
    return value is None or value is MISSING or (isinstance(value, str) and not value.strip())


def _scalar_from_widget(param: ParamSpec, value: Any) -> Any:
    target = param.type
    if isinstance(target, type) and issubclass(target, enum.Enum):
        return _to_enum(target, value)
    if target is bool:
        return bool(value)
    if target is int:
        return int(float(value)) if not isinstance(value, int) else value
    if target is float:
        return float(value)
    if target is Path:
        return value if isinstance(value, Path) else Path(str(value))
    if target is str or target is None:
        return str(value)
    if isinstance(target, type) and isinstance(value, target):
        return value
    if isinstance(target, type):
        # A custom annotated type: let it parse its own string form, but never
        # fail the submission over it -- the raw value is better than an error.
        try:
            return target(value)
        except (TypeError, ValueError):
            return value
    return value


def _to_enum(enum_cls: type[enum.Enum], value: Any) -> Any:
    if isinstance(value, enum_cls):
        return value
    for member in enum_cls:
        if value == member.name or value == member.value or str(value) == str(member.value):
            return member
    return value
