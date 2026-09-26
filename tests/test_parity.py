"""The same CLI, described five ways, must produce the same form.

This is the load-bearing test of the whole design: if an adapter drifts, the
profiles stop matching. It deliberately compares the *rendered* shape -- widget
kind, requiredness, choices, the value the widget starts with -- rather than raw
Python types, because ``mode`` is legitimately an Enum in cyclopts, a plain
string in click and a Typer-erased choice in Typer while rendering identically.
"""

from __future__ import annotations

import pytest

from fixtures_cli import BUILDERS
from nicegui_autoform import build_spec, choose_widget
from nicegui_autoform.spec import CommandSpec
from nicegui_autoform.values import to_widget

EXPECTED = {
    "data": ("upload", True, False, False, None, None),
    "epochs": ("int", False, False, False, None, 10),
    "lr": ("float", False, False, False, None, 0.001),
    "mode": ("select", False, False, False, ("fast", "slow"), "fast"),
    "verbose": ("checkbox", False, False, True, None, False),
    "tags": ("chips", False, True, False, None, []),
}


def profile(spec: CommandSpec) -> dict[str, tuple]:
    return {
        p.name: (
            str(choose_widget(p)),
            p.required,
            p.multiple,
            p.is_flag,
            p.choices,
            to_widget(p, p.default),
        )
        for p in spec.params
    }


@pytest.mark.parametrize(("name", "builder"), BUILDERS, ids=[n for n, _ in BUILDERS])
def test_all_frameworks_render_the_same_form(name, builder):
    target, command = builder()
    assert profile(build_spec(target, command)) == EXPECTED


@pytest.mark.parametrize(("name", "builder"), BUILDERS, ids=[n for n, _ in BUILDERS])
def test_parameter_order_follows_the_cli(name, builder):
    target, command = builder()
    spec = build_spec(target, command)
    assert [p.name for p in spec.params] == list(EXPECTED)


@pytest.mark.parametrize(("name", "builder"), BUILDERS, ids=[n for n, _ in BUILDERS])
def test_help_text_is_carried_through(name, builder):
    target, command = builder()
    spec = build_spec(target, command)
    assert spec.get("epochs").help == "number of epochs"
    assert spec.get("verbose").help == "chatty"


@pytest.mark.parametrize(("name", "builder"), BUILDERS, ids=[n for n, _ in BUILDERS])
def test_callback_is_the_original_function_except_for_argparse(name, builder):
    target, command = builder()
    spec = build_spec(target, command)
    if name == "argparse":
        assert spec.callback is None  # a parser has nothing to call
    else:
        assert callable(spec.callback)
