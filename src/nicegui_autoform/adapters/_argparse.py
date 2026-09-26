"""Adapter for ``argparse``.

``ArgumentParser`` keeps its actions on the private ``_actions`` list, which has
been stable across the whole life of the module. Unlike the other frameworks an
``ArgumentParser`` has no callback -- parsing produces a ``Namespace`` and the
program takes it from there -- so :attr:`CommandSpec.callback` is ``None`` and
:class:`~nicegui_autoform.form.AutoForm` requires an explicit ``on_submit``.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ..spec import MISSING, CommandSpec, ParamSpec

name = "argparse"

_SKIPPED_ACTIONS = (argparse._HelpAction, argparse._VersionAction, argparse._SubParsersAction)
_FLAG_ACTIONS = (argparse._StoreTrueAction, argparse._StoreFalseAction)


def matches(target: Any) -> bool:
    return isinstance(target, argparse.ArgumentParser)


def build(target: Any, command: str | None = None) -> CommandSpec:
    parser = _resolve_command(target, command)
    sections = _sections(parser)

    params = []
    for action in parser._actions:
        if isinstance(action, _SKIPPED_ACTIONS) or action.help == argparse.SUPPRESS:
            continue
        if action.dest == argparse.SUPPRESS:
            continue
        params.append(_to_param(action, sections.get(id(action))))

    return CommandSpec(
        name=parser.prog or "",
        help=_first_line(parser.description),
        params=tuple(params),
        callback=None,
        source=name,
        extras={"parser": parser},
    )


def _resolve_command(parser: Any, command: str | None) -> Any:
    subparsers = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    if command is None:
        return parser
    for action in subparsers:
        if command in action.choices:
            return action.choices[command]
    available = sorted({name for a in subparsers for name in a.choices})
    raise KeyError(f"{command!r} is not a subcommand of this parser; available: {available}")


def _sections(parser: Any) -> dict[int, str]:
    """Map each action to its argument group title, skipping argparse's defaults."""
    default_titles = {"positional arguments", "options", "optional arguments"}
    sections: dict[int, str] = {}
    for group in parser._action_groups:
        title = (group.title or "").strip()
        if not title or title.lower() in default_titles:
            continue
        for action in group._group_actions:
            sections[id(action)] = title
    return sections


def _to_param(action: Any, section: str | None) -> ParamSpec:
    is_flag = isinstance(action, _FLAG_ACTIONS)
    scalar = _resolve_type(action, is_flag)
    multiple = (
        isinstance(action, argparse._AppendAction)
        or action.nargs in ("+", "*")
        or (isinstance(action.nargs, int) and action.nargs > 1)
    )

    positional = not action.option_strings
    required = bool(action.required) or (positional and action.nargs not in ("?", "*"))
    default = MISSING if (required or action.default is None and positional) else action.default
    if default is argparse.SUPPRESS:
        default = MISSING

    choices = tuple(str(c) for c in action.choices) if action.choices else None

    return ParamSpec(
        name=action.dest,
        path=(action.dest,),
        cli_name=action.option_strings[0] if action.option_strings else action.dest,
        annotation=action.type,
        type=scalar,
        required=required,
        default=default,
        help=_clean(action.help),
        choices=choices,
        multiple=bool(multiple),
        nargs=action.nargs if isinstance(action.nargs, int) and action.nargs > 1 else None,
        is_flag=is_flag,
        section=section,
    )


def _resolve_type(action: Any, is_flag: bool) -> Any:
    if is_flag:
        return bool
    converter = action.type
    if converter is None:
        return str
    if isinstance(converter, argparse.FileType):
        return Path
    if isinstance(converter, type):
        return converter
    # A plain callable converter (e.g. a lambda) tells us nothing useful; a text
    # input feeding the callable is the honest rendering.
    return str


def _clean(text: str | None) -> str | None:
    return " ".join(text.split()) if text else None


def _first_line(text: str | None) -> str | None:
    if not text:
        return None
    stripped = text.strip()
    return stripped.split("\n\n")[0].strip() or None
