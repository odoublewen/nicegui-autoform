"""The IR itself: lookup, exclusion, widget overrides and nested binding."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from nicegui_autoform import MISSING, CommandSpec, ContainerSpec, ParamSpec, WidgetKind


def param(name, path=None, **kwargs) -> ParamSpec:
    return ParamSpec(name=name, path=path or (name,), cli_name=f"--{name}", **kwargs)


@dataclass
class Config:
    data: Path
    epochs: int = 10


def test_duplicate_paths_are_rejected():
    with pytest.raises(ValueError, match="duplicate parameter path"):
        CommandSpec(name="x", params=(param("a"), param("a")))


def test_get_accepts_name_dotted_string_and_tuple():
    spec = CommandSpec(name="x", params=(param("epochs", ("config", "epochs")),))
    assert spec.get("epochs").name == "epochs"
    assert spec.get("config.epochs").name == "epochs"
    assert spec.get(("config", "epochs")).name == "epochs"
    with pytest.raises(KeyError):
        spec.get("nope")


def test_visible_params_drops_hidden_and_excluded():
    spec = CommandSpec(
        name="x",
        params=(
            param("a"),
            param("b", hidden=True),
            param("c"),
            param("seed", ("config", "seed")),
        ),
    )
    visible = spec.visible_params(frozenset({"c", "config.seed"}))
    assert [p.name for p in visible] == ["a"]


def test_with_widgets_overrides_by_name_or_path():
    spec = CommandSpec(name="x", params=(param("a"), param("b", ("cfg", "b"))))
    overridden = spec.with_widgets({"a": WidgetKind.TEXTAREA, "cfg.b": WidgetKind.PASSWORD})
    assert overridden.get("a").widget is WidgetKind.TEXTAREA
    assert overridden.get(("cfg", "b")).widget is WidgetKind.PASSWORD
    assert spec.get("a").widget is None  # the original is untouched


def test_bind_returns_plain_kwargs_for_flat_params():
    spec = CommandSpec(name="x", params=(param("epochs"), param("lr")))
    args, kwargs = spec.bind({("epochs",): 5, ("lr",): 0.1})
    assert args == ()
    assert kwargs == {"epochs": 5, "lr": 0.1}


def test_bind_drops_missing_so_callback_defaults_apply():
    spec = CommandSpec(name="x", params=(param("epochs"), param("lr")))
    _, kwargs = spec.bind({("epochs",): MISSING, ("lr",): 0.1})
    assert kwargs == {"lr": 0.1}


def test_bind_rebuilds_a_nested_container():
    spec = CommandSpec(
        name="x",
        params=(param("data", ("config", "data")), param("epochs", ("config", "epochs")),
                param("seed")),
        containers=(ContainerSpec(path=("config",), factory=Config, title="Config"),),
    )
    _, kwargs = spec.bind(
        {("config", "data"): Path("/tmp/x"), ("config", "epochs"): 3, ("seed",): 7}
    )
    assert kwargs == {"config": Config(data=Path("/tmp/x"), epochs=3), "seed": 7}


def test_bind_rebuilds_containers_deepest_first():
    @dataclass
    class Inner:
        x: int = 1

    @dataclass
    class Outer:
        inner: Inner
        y: int = 2

    spec = CommandSpec(
        name="x",
        params=(param("x", ("outer", "inner", "x")), param("y", ("outer", "y"))),
        containers=(
            ContainerSpec(path=("outer",), factory=Outer, title="Outer"),
            ContainerSpec(path=("outer", "inner"), factory=Inner, title="Inner"),
        ),
    )
    _, kwargs = spec.bind({("outer", "inner", "x"): 9, ("outer", "y"): 8})
    assert kwargs == {"outer": Outer(inner=Inner(x=9), y=8)}


def test_bind_passes_positional_only_params_as_args():
    spec = CommandSpec(name="x", params=(param("a", positional_only=True), param("b")))
    args, kwargs = spec.bind({("a",): 1, ("b",): 2})
    assert args == (1,)
    assert kwargs == {"b": 2}


def test_defaults_snapshot():
    spec = CommandSpec(name="x", params=(param("a", default=1), param("b")))
    assert spec.defaults() == {("a",): 1, ("b",): MISSING}


def test_label_titlecases_the_name():
    assert param("learning_rate").label == "Learning Rate"
