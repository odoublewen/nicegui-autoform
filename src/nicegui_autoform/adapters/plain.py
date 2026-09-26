"""Adapter for a bare ``@dataclass`` or an annotated function.

This is the fallback, and the only adapter that needs no CLI framework at all.
It preserves the behaviour of the original ``autoform.py``: the
``ExcludeFromAutoform`` annotation marker, the ``autoform_exclude`` field
metadata escape hatch, and reading help text out of a ``cyclopts.Parameter``
annotation when cyclopts happens to be importable.
"""

from __future__ import annotations

import inspect
import sys
from dataclasses import MISSING as DC_MISSING
from dataclasses import fields, is_dataclass
from typing import Any, get_type_hints

from .._introspect import annotated_metadata, choices_of, has_exclude_marker, resolve
from ..spec import MISSING, CommandSpec, ParamSpec

name = "plain"


def matches(target: Any) -> bool:
    return is_dataclass(target) or inspect.isfunction(target) or inspect.ismethod(target)


def build(target: Any, command: str | None = None) -> CommandSpec:
    if command is not None:
        raise ValueError(f"{name} targets have no subcommands, so command={command!r} is invalid")
    if is_dataclass(target):
        return _from_dataclass(target)
    return _from_function(target)


def _from_dataclass(cls: Any) -> CommandSpec:
    cls = cls if isinstance(cls, type) else type(cls)
    hints = get_type_hints(cls, include_extras=True)

    params = []
    for f in fields(cls):
        if not f.init:
            continue
        hint = hints.get(f.name, f.type)
        default = MISSING
        if f.default is not DC_MISSING:
            default = f.default
        elif f.default_factory is not DC_MISSING:  # type: ignore[misc]
            default = f.default_factory()  # type: ignore[misc]
        params.append(
            _to_param(
                f.name,
                hint,
                default,
                hidden=bool(f.metadata.get("autoform_exclude")) or has_exclude_marker(hint),
            )
        )

    return CommandSpec(
        name=cls.__name__,
        help=_first_line(_authored_doc(cls)),
        params=tuple(params),
        callback=cls,
        source=name,
    )


def _from_function(fn: Any) -> CommandSpec:
    hints = get_type_hints(fn, include_extras=True)
    signature = inspect.signature(fn)

    params = []
    for p in signature.parameters.values():
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        hint = hints.get(p.name, str)
        default = MISSING if p.default is inspect.Parameter.empty else p.default
        params.append(
            _to_param(
                p.name,
                hint,
                default,
                hidden=has_exclude_marker(hint),
                positional_only=p.kind is p.POSITIONAL_ONLY,
            )
        )

    return CommandSpec(
        name=fn.__name__,
        help=_first_line(fn.__doc__),
        params=tuple(params),
        callback=fn,
        source=name,
    )


def _to_param(
    param_name: str,
    hint: Any,
    default: Any,
    *,
    hidden: bool = False,
    positional_only: bool = False,
) -> ParamSpec:
    scalar, multiple = resolve(hint)
    return ParamSpec(
        name=param_name,
        path=(param_name,),
        cli_name=f"--{param_name.replace('_', '-')}",
        annotation=hint,
        type=scalar,
        required=default is MISSING,
        default=default,
        help=_help_from_metadata(hint),
        choices=choices_of(hint),
        multiple=multiple,
        is_flag=scalar is bool,
        hidden=hidden,
        positional_only=positional_only,
    )


def _help_from_metadata(hint: Any) -> str | None:
    """Help text from a ``cyclopts.Parameter`` in the ``Annotated`` metadata.

    Later parameters override earlier ones, matching how cyclopts resolves them.
    """
    cyclopts = sys.modules.get("cyclopts")
    if cyclopts is None:
        return None
    found = None
    for meta in annotated_metadata(hint):
        if isinstance(meta, cyclopts.Parameter) and meta.help:
            found = meta.help
    return found.strip() if found else None


def _authored_doc(cls: type) -> str | None:
    """The class docstring, unless @dataclass synthesised one from the signature."""
    doc = cls.__doc__
    if doc and doc.startswith(f"{cls.__name__}("):
        return None
    return doc


def _first_line(text: str | None) -> str | None:
    if not text:
        return None
    stripped = text.strip()
    return stripped.split("\n\n")[0].strip() or None
