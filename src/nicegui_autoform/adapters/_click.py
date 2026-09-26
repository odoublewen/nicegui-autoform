"""Adapter for click.

``Command.params`` gives fully resolved ``Option``/``Argument`` objects. The one
sharp edge is the default sentinel: click 8.5 reports an unset default as
``click.core.UNSET`` rather than ``None``, which :mod:`nicegui_autoform._compat`
normalises.
"""

from __future__ import annotations

import enum
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, get_type_hints

from .._compat import TYPER_INJECTED_PARAMS, click_default
from .._introspect import resolve
from ..spec import MISSING, CommandSpec, ParamSpec

name = "click"


def matches(target: Any) -> bool:
    click = sys.modules.get("click")
    return click is not None and isinstance(target, click.Command)


def build(target: Any, command: str | None = None, *, source: str = name) -> CommandSpec:
    cmd = _resolve_command(target, command)

    params = []
    for param in cmd.params:
        if getattr(param, "hidden", False) or param.name in TYPER_INJECTED_PARAMS:
            continue
        params.append(_to_param(param))

    return CommandSpec(
        name=cmd.name or "",
        help=_first_line(cmd.help),
        params=_enrich_from_callback(tuple(params), cmd.callback),
        callback=cmd.callback,
        source=source,
        extras={"click_command": cmd},
    )


def _enrich_from_callback(params: tuple[ParamSpec, ...], callback: Any) -> tuple[ParamSpec, ...]:
    """Recover types that the click ``ParamType`` could not express.

    Typer's ``TyperChoice`` keeps only the choice strings, discarding the Enum
    class the callback actually expects -- but the callback's own annotation
    still has it. Since we call that callback directly, its annotation is the
    authority whenever click could only tell us ``str``.
    """
    if callback is None:
        return params

    try:
        hints = get_type_hints(callback)
    except Exception:  # unresolvable forward refs; the click types stand alone
        return params

    enriched = []
    for param in params:
        hint = hints.get(param.name)
        if hint is None:
            enriched.append(param)
            continue
        scalar, multiple = resolve(hint)
        is_enum = isinstance(scalar, type) and issubclass(scalar, enum.Enum)
        if is_enum or param.type is str:
            enriched.append(
                replace(param, type=scalar, annotation=hint, multiple=param.multiple or multiple)
            )
        else:
            enriched.append(param)
    return tuple(enriched)


def _resolve_command(target: Any, command: str | None) -> Any:
    """Narrow a group to a single command.

    Groups are identified by having a ``commands`` mapping rather than by
    ``isinstance(target, click.Group)``: Typer's ``TyperGroup`` subclasses its
    own vendored click, so the isinstance check would quietly treat a group as a
    single command.
    """
    subcommands = getattr(target, "commands", None)
    if not subcommands:
        if command is not None and command != target.name:
            raise KeyError(
                f"{target.name!r} is a single command, not a group containing {command!r}"
            )
        return target

    names = [n for n, c in subcommands.items() if not getattr(c, "hidden", False)]
    if command is not None:
        if command not in subcommands:
            raise KeyError(f"{command!r} is not a command of this group; available: {names}")
        return subcommands[command]
    if len(names) == 1:
        return subcommands[names[0]]
    raise ValueError(
        f"this group has {len(names)} commands, so command= is required; available: {names}"
    )


def _to_param(param: Any) -> ParamSpec:
    scalar, choices, minimum, maximum = _resolve_type(param.type)
    default = click_default(param)
    nargs = param.nargs if isinstance(param.nargs, int) else None
    multiple = bool(param.multiple) or (nargs is not None and nargs != 1)

    if multiple and (default is MISSING or default is None or default in ((), [])):
        # Parsing a multiple option that was never passed yields an empty tuple,
        # never None -- so an empty list is the honest starting value however
        # this click version reports the unset default (UNSET since 8.5, None
        # before that).
        default = [] if not param.required else MISSING
    if param.required:
        default = MISSING

    opts = list(param.opts or [])
    secondary = list(param.secondary_opts or [])

    return ParamSpec(
        name=param.name,
        path=(param.name,),
        cli_name=opts[0] if opts else param.name,
        annotation=param.type,
        type=scalar,
        required=bool(param.required),
        default=default,
        help=_clean(getattr(param, "help", None)),
        choices=choices,
        multiple=multiple,
        nargs=nargs if nargs not in (None, 1, -1) else None,
        is_flag=bool(getattr(param, "is_flag", False)) or scalar is bool,
        negative_cli_name=secondary[0] if secondary else None,
        section=getattr(param, "rich_help_panel", None),
        env_var=_env_vars(param),
        minimum=minimum,
        maximum=maximum,
    )


def _resolve_type(
    param_type: Any,
) -> tuple[Any, tuple[str, ...] | None, float | None, float | None]:
    """Map a click ``ParamType`` to ``(python type, choices, minimum, maximum)``.

    Deliberately duck-typed rather than ``isinstance``-based: Typer ships its own
    vendored copy of click, so ``typer.models.TyperPath`` is not a
    ``click.Path`` and its scalar types report ``name='int'`` where real click
    reports ``'integer'``. Matching on the MRO's class names plus the type's own
    ``name`` covers both, and keeps working across click releases.
    """
    class_names = " ".join(c.__name__ for c in type(param_type).__mro__)
    type_name = (getattr(param_type, "name", "") or "").lower()

    choices = getattr(param_type, "choices", None)
    if choices is not None:
        return str, tuple(_choice_label(c) for c in choices), None, None

    if "IntRange" in class_names or type_name == "integer range":
        return int, None, _bound(param_type, "min"), _bound(param_type, "max")
    if "FloatRange" in class_names or type_name == "float range":
        return float, None, _bound(param_type, "min"), _bound(param_type, "max")
    if "Path" in class_names or "File" in class_names or type_name in {"path", "filename", "file"}:
        return Path, None, None, None
    if "DateTime" in class_names or type_name == "datetime":
        return str, None, None, None
    if "Bool" in class_names or type_name in {"boolean", "bool"}:
        return bool, None, None, None
    if "Int" in class_names or type_name in {"integer", "int"}:
        return int, None, None, None
    if "Float" in class_names or type_name == "float":
        return float, None, None, None
    return str, None, None, None


def _choice_label(choice: Any) -> str:
    """The string a choice is shown and submitted as.

    ``click.Choice`` accepts an Enum directly and keeps its members, whereas
    Typer flattens an Enum to its values before click ever sees it. Preferring a
    string ``.value`` makes both produce the same labels.
    """
    if isinstance(choice, enum.Enum):
        return choice.value if isinstance(choice.value, str) else choice.name
    return str(choice)


def _bound(param_type: Any, attr: str) -> float | None:
    value = getattr(param_type, attr, None)
    return float(value) if value is not None else None


def _env_vars(param: Any) -> tuple[str, ...]:
    envvar = getattr(param, "envvar", None)
    if not envvar:
        return ()
    return (envvar,) if isinstance(envvar, str) else tuple(envvar)


def _clean(text: str | None) -> str | None:
    return " ".join(text.split()) if text else None


def _first_line(text: str | None) -> str | None:
    if not text:
        return None
    stripped = text.strip()
    return stripped.split("\n\n")[0].strip() or None
