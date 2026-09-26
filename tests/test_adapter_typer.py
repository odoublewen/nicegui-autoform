"""Typer specifics: injected completion params, and its vendored click."""

from __future__ import annotations

import enum
from pathlib import Path
from typing import Annotated

import pytest
import typer

from nicegui_autoform import build_spec


class Mode(enum.StrEnum):
    fast = "fast"
    slow = "slow"


def test_injected_completion_options_are_dropped():
    # A Typer app created without add_completion=False grows two extra options
    # that have nothing to do with the command.
    app = typer.Typer()

    @app.command()
    def one(x: int = 1): ...

    @app.command()
    def two(y: int = 2): ...

    spec = build_spec(app, "one")
    assert [p.name for p in spec.params] == ["x"]


def test_typers_vendored_click_types_still_resolve():
    # typer.models.TyperPath is not a click.Path, and its int type reports
    # name='int' where real click reports 'integer'.
    app = typer.Typer(add_completion=False)

    @app.command()
    def cmd(data: Path, epochs: int = 10, lr: float = 0.5, flag: bool = False): ...

    spec = build_spec(app)
    assert [p.type for p in spec.params] == [Path, int, float, bool]


def test_enum_erased_by_typer_is_recovered_from_the_callback():
    # TyperChoice keeps only the choice strings, so the Enum the callback
    # expects has to come from its annotation.
    app = typer.Typer(add_completion=False)

    @app.command()
    def cmd(mode: Mode = Mode.fast): ...

    param = build_spec(app).get("mode")
    assert param.type is Mode
    assert param.choices == ("fast", "slow")


def test_help_from_an_annotated_option():
    app = typer.Typer(add_completion=False)

    @app.command()
    def cmd(epochs: Annotated[int, typer.Option(help="number of epochs")] = 10): ...

    assert build_spec(app).get("epochs").help == "number of epochs"


def test_rich_help_panel_becomes_a_section():
    app = typer.Typer(add_completion=False)

    @app.command()
    def cmd(
        x: Annotated[int, typer.Option(rich_help_panel="Advanced")] = 1,
        y: int = 2,
    ): ...

    spec = build_spec(app)
    assert spec.get("x").section == "Advanced"
    assert spec.get("y").section is None


def test_single_command_app_needs_no_command_name():
    app = typer.Typer(add_completion=False)

    @app.command()
    def only(x: int = 1): ...

    assert [p.name for p in build_spec(app).params] == ["x"]


def test_multi_command_app_requires_a_command_name():
    app = typer.Typer(add_completion=False)

    @app.command()
    def one(): ...

    @app.command()
    def two(): ...

    with pytest.raises(ValueError, match="command= is required"):
        build_spec(app)


def test_the_callback_is_reachable_and_callable():
    app = typer.Typer(add_completion=False)

    @app.command()
    def cmd(x: int = 1) -> int:
        return x * 2

    spec = build_spec(app)
    args, kwargs = spec.bind({("x",): 21})
    assert spec.callback is not None
    assert spec.callback(*args, **kwargs) == 42
