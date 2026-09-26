"""Adapter for cyclopts.

Everything needed is public API: ``App.assemble_argument_collection()`` yields an
``ArgumentCollection`` whose entries already carry resolved hints, defaults,
choices and negative flag names. Dataclass parameters appear as a container
argument with ``children``, plus one leaf per field -- for both the nested
(``--config.epochs``) and flattened (``Parameter(name="*")``) styles.
"""

from __future__ import annotations

import inspect
import sys
from typing import Any

from .._introspect import resolve
from ..spec import MISSING, CommandSpec, ContainerSpec, ParamSpec

name = "cyclopts"


def matches(target: Any) -> bool:
    cyclopts = sys.modules.get("cyclopts")
    return cyclopts is not None and isinstance(target, cyclopts.App)


def build(target: Any, command: str | None = None) -> CommandSpec:
    app = _resolve_command(target, command)
    collection = app.assemble_argument_collection(parse_docstring=True)

    params: list[ParamSpec] = []
    containers: list[ContainerSpec] = []
    for root in _roots(collection):
        # A root argument names a callback parameter; its descendants' ``keys``
        # are relative to it, so the structural path is prefix + keys.
        prefix = (root.field_info.names[0],)
        _walk(root, prefix, params, containers)

    sections = {c.path: c.title for c in containers}
    params = [
        p if len(p.path) == 1 else _with_section(p, sections.get(p.path[:-1])) for p in params
    ]

    return CommandSpec(
        name=_app_name(app),
        help=_first_line(app.help),
        params=tuple(params),
        containers=tuple(containers),
        callback=app.default_command,
        source=name,
    )


def _resolve_command(app: Any, command: str | None) -> Any:
    if command is not None:
        try:
            return app[command]
        except (KeyError, IndexError):
            raise KeyError(
                f"{command!r} is not a command of this app; available: {_command_names(app)}"
            ) from None
    if app.default_command is not None:
        return app
    names = _command_names(app)
    if len(names) == 1:
        return app[names[0]]
    raise ValueError(
        f"this app has {len(names)} commands, so command= is required; available: {names}"
    )


def _command_names(app: Any) -> list[str]:
    seen: dict[int, str] = {}
    for key in app:
        if key.startswith("-"):
            continue  # --help / -h / --version are registered like commands
        seen.setdefault(id(app[key]), key)
    return list(seen.values())


def _app_name(app: Any) -> str:
    value = app.name
    if isinstance(value, (tuple, list)):
        return str(value[0]) if value else ""
    return str(value)


def _roots(collection: Any) -> list[Any]:
    """The arguments that are not a descendant of another argument."""
    descendants = {id(child) for arg in collection for child in arg.children_recursive}
    return [arg for arg in collection if id(arg) not in descendants]


def _walk(
    argument: Any,
    prefix: tuple[str, ...],
    params: list[ParamSpec],
    containers: list[ContainerSpec],
) -> None:
    path = prefix + tuple(argument.keys)
    if argument.children:
        containers.append(
            ContainerSpec(
                path=path,
                factory=argument.hint,
                title=_title(path[-1]),
                help=argument.parameter.help,
            )
        )
        for child in argument.children:
            _walk(child, prefix, params, containers)
        return
    params.append(_to_param(argument, path))


def _to_param(argument: Any, path: tuple[str, ...]) -> ParamSpec:
    hint = argument.hint
    scalar, multiple = resolve(hint)
    default = argument.field_info.default
    if default is inspect.Parameter.empty:
        default = MISSING
    negatives = tuple(argument.negatives or ())
    kind = argument.field_info.kind

    return ParamSpec(
        name=argument.field_info.names[0],
        path=path,
        cli_name=argument.name,
        annotation=hint,
        type=scalar,
        required=bool(argument.required),
        default=default,
        help=argument.parameter.help,
        choices=argument.get_choices(),
        multiple=multiple,
        is_flag=scalar is bool,
        negative_cli_name=negatives[0] if negatives else None,
        hidden=not argument.show,
        env_var=tuple(argument.parameter.env_var or ()),
        positional_only=kind is inspect.Parameter.POSITIONAL_ONLY and len(path) == 1,
    )


def _with_section(param: ParamSpec, section: str | None) -> ParamSpec:
    from dataclasses import replace

    return replace(param, section=section) if section else param


def _title(text: str) -> str:
    return text.replace("_", " ").title()


def _first_line(text: str | None) -> str | None:
    if not text:
        return None
    stripped = text.strip()
    return stripped.split("\n\n")[0].strip() or None
