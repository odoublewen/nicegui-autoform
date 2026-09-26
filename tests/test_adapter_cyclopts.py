"""Cyclopts specifics: dataclass flattening, docstring help, negative flags."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal

import cyclopts
import pytest

from nicegui_autoform import MISSING, build_spec


@dataclass
class Inner:
    """Inner.

    Parameters
    ----------
    x: int
        the x value
    """

    x: int = 1


@dataclass
class Config:
    """Training configuration.

    Parameters
    ----------
    data: Path
        input data file
    epochs: int
        number of epochs
    """

    data: Path
    epochs: int = 10
    inner: Inner = field(default_factory=Inner)


def app_with(fn) -> cyclopts.App:
    app = cyclopts.App(name="demo")
    app.command(fn)
    return app


def test_docstring_help_is_read_from_the_command():
    def train(epochs: int = 10):
        """Train.

        Parameters
        ----------
        epochs: int
            number of epochs
        """

    spec = build_spec(app_with(train), "train")
    assert spec.get("epochs").help == "number of epochs"


def test_help_from_a_parameter_annotation():
    def train(x: Annotated[int, cyclopts.Parameter(help="explicit help")] = 1): ...

    assert build_spec(app_with(train), "train").get("x").help == "explicit help"


def test_negative_flag_name_is_captured():
    def train(verbose: bool = False): ...

    param = build_spec(app_with(train), "train").get("verbose")
    assert param.is_flag
    assert param.negative_cli_name == "--no-verbose"


def test_literal_and_enum_both_yield_choices():
    def train(mode: Literal["fast", "slow"] = "fast"): ...

    assert build_spec(app_with(train), "train").get("mode").choices == ("fast", "slow")


def test_required_parameter_has_no_default():
    def train(data: Path): ...

    param = build_spec(app_with(train), "train").get("data")
    assert param.required and param.default is MISSING


def test_nested_dataclass_flattens_to_leaves_with_dotted_cli_names():
    def train(config: Config, seed: int = 0): ...

    spec = build_spec(app_with(train), "train")
    assert [".".join(p.path) for p in spec.params] == [
        "config.data",
        "config.epochs",
        "config.inner.x",
        "seed",
    ]
    assert spec.get("config.epochs").cli_name == "--config.epochs"
    assert spec.get("config.epochs").section == "Config"
    assert spec.get("config.inner.x").section == "Inner"


def test_flattened_dataclass_keeps_the_same_structural_paths():
    def train(config: Annotated[Config, cyclopts.Parameter(name="*")], seed: int = 0): ...

    spec = build_spec(app_with(train), "train")
    # The CLI names lose the prefix, but the paths must not -- they are what
    # bind() uses to rebuild the dataclass.
    assert spec.get("config.epochs").cli_name == "--epochs"
    assert [".".join(p.path) for p in spec.params][:2] == ["config.data", "config.epochs"]


def test_dataclass_field_help_comes_from_the_dataclass_docstring():
    def train(config: Config): ...

    spec = build_spec(app_with(train), "train")
    assert spec.get("config.epochs").help == "number of epochs"
    assert spec.get("config.inner.x").help == "the x value"


def test_containers_are_recorded_for_rebuilding():
    def train(config: Config): ...

    spec = build_spec(app_with(train), "train")
    assert {c.path: c.factory for c in spec.containers} == {
        ("config",): Config,
        ("config", "inner"): Inner,
    }


def test_bind_round_trips_a_nested_dataclass():
    def train(config: Config, seed: int = 0): ...

    spec = build_spec(app_with(train), "train")
    _, kwargs = spec.bind(
        {
            ("config", "data"): Path("/tmp/d"),
            ("config", "epochs"): 3,
            ("config", "inner", "x"): 9,
            ("seed",): 7,
        }
    )
    assert kwargs == {"config": Config(Path("/tmp/d"), 3, Inner(9)), "seed": 7}


def test_single_command_app_needs_no_command_name():
    def only(x: int = 1): ...

    assert build_spec(app_with(only)).name == "only"


def test_multi_command_app_requires_a_command_name():
    app = cyclopts.App(name="demo")
    app.command(lambda: None, name="a")
    app.command(lambda: None, name="b")
    with pytest.raises(ValueError, match="command= is required"):
        build_spec(app)


def test_unknown_command_names_the_available_ones():
    def train(x: int = 1): ...

    with pytest.raises(KeyError, match="available"):
        build_spec(app_with(train), "nope")


def test_positional_only_parameters_are_marked():
    def train(a: int, /, b: int = 2): ...

    spec = build_spec(app_with(train), "train")
    assert spec.get("a").positional_only
    assert not spec.get("b").positional_only
    args, kwargs = spec.bind({("a",): 1, ("b",): 2})
    assert args == (1,) and kwargs == {"b": 2}
