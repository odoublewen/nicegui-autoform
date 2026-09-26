"""Widget selection. Pure -- no NiceGUI runtime required."""

from __future__ import annotations

import enum
from pathlib import Path

import pytest

from nicegui_autoform import ParamSpec, WidgetKind, choose_widget
from nicegui_autoform.widgets import label_for


class Mode(enum.StrEnum):
    fast = "fast"


def param(**kwargs) -> ParamSpec:
    kwargs.setdefault("name", "p")
    kwargs.setdefault("path", ("p",))
    kwargs.setdefault("cli_name", "--p")
    return ParamSpec(**kwargs)


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"type": str}, WidgetKind.TEXT),
        ({"type": int}, WidgetKind.INT),
        ({"type": float}, WidgetKind.FLOAT),
        ({"type": bool}, WidgetKind.CHECKBOX),
        ({"type": bool, "is_flag": True}, WidgetKind.CHECKBOX),
        ({"type": Path}, WidgetKind.UPLOAD),
        ({"type": str, "multiple": True}, WidgetKind.CHIPS),
        ({"type": str, "choices": ("a", "b")}, WidgetKind.SELECT),
        ({"type": str, "choices": ("a", "b"), "multiple": True}, WidgetKind.MULTISELECT),
        ({"type": Mode, "choices": ("fast",)}, WidgetKind.SELECT),
    ],
)
def test_widget_selection(kwargs, expected):
    assert choose_widget(param(**kwargs)) is expected


def test_choices_win_over_the_underlying_type():
    # An int with a bounded set of values is still a dropdown.
    assert choose_widget(param(type=int, choices=("1", "2"))) is WidgetKind.SELECT


def test_an_explicit_override_wins_over_everything():
    p = param(type=int, choices=("1",), widget=WidgetKind.TEXTAREA)
    assert choose_widget(p) is WidgetKind.TEXTAREA


def test_required_fields_are_marked_in_the_label():
    assert label_for(param(name="learning_rate", required=True)) == "Learning Rate *"
    assert label_for(param(name="learning_rate", required=False)) == "Learning Rate"
