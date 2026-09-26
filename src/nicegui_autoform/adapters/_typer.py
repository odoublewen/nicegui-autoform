"""Adapter for Typer.

Typer builds on click, so ``typer.main.get_command()`` hands us a click
``Command`` (or ``TyperGroup``) and the click adapter does the rest. The only
Typer-specific work is resolving the command and dropping the completion options
Typer injects unless the app was created with ``add_completion=False``.
"""

from __future__ import annotations

import sys
from typing import Any

from ..spec import CommandSpec
from . import _click

name = "typer"


def matches(target: Any) -> bool:
    typer = sys.modules.get("typer")
    return typer is not None and isinstance(target, typer.Typer)


def build(target: Any, command: str | None = None) -> CommandSpec:
    import typer.main

    return _click.build(typer.main.get_command(target), command, source=name)
