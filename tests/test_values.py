"""Conversion between Python values and NiceGUI widget values."""

from __future__ import annotations

import enum
from pathlib import Path

import pytest

from nicegui_autoform import MISSING, ParamSpec, from_widget, to_widget


class Mode(enum.StrEnum):
    fast = "fast"
    slow = "slow"


def param(**kwargs) -> ParamSpec:
    kwargs.setdefault("name", "p")
    kwargs.setdefault("path", ("p",))
    kwargs.setdefault("cli_name", "--p")
    return ParamSpec(**kwargs)


def test_to_widget_renders_an_enum_as_its_choice_string():
    p = param(type=Mode, choices=("fast", "slow"), default=Mode.slow)
    assert to_widget(p, Mode.slow) == "slow"


def test_to_widget_renders_a_path_as_text():
    assert to_widget(param(type=Path), Path("/tmp/x")) == "/tmp/x"


def test_to_widget_gives_an_empty_list_for_a_missing_multiple():
    assert to_widget(param(type=str, multiple=True), MISSING) == []


def test_to_widget_gives_false_for_a_missing_flag():
    assert to_widget(param(type=bool, is_flag=True), MISSING) is False


def test_from_widget_converts_a_choice_string_back_to_its_enum_member():
    p = param(type=Mode, choices=("fast", "slow"))
    assert from_widget(p, "slow") is Mode.slow


def test_from_widget_narrows_a_number_widgets_float_to_int():
    # ui.number always yields a float, even for an int field.
    assert from_widget(param(type=int), 3.0) == 3
    assert isinstance(from_widget(param(type=int), 3.0), int)


def test_from_widget_builds_a_path():
    assert from_widget(param(type=Path), "/tmp/x") == Path("/tmp/x")


def test_from_widget_returns_missing_for_an_empty_optional_without_a_default():
    assert from_widget(param(type=str), "") is MISSING
    assert from_widget(param(type=str), None) is MISSING


def test_from_widget_falls_back_to_the_default_for_an_emptied_field():
    assert from_widget(param(type=int, default=10), None) == 10


def test_from_widget_splits_free_text_for_a_multiple_field():
    p = param(type=str, multiple=True)
    assert from_widget(p, "a, b ,c") == ["a", "b", "c"]


def test_from_widget_converts_each_element_of_a_multiple_field():
    p = param(type=int, multiple=True)
    assert from_widget(p, ["1", "2"]) == [1, 2]


def test_from_widget_coerces_anything_to_a_flag():
    assert from_widget(param(type=bool, is_flag=True), None) is False
    assert from_widget(param(type=bool, is_flag=True), True) is True


@pytest.mark.parametrize("value", ["not-a-number", ""])
def test_from_widget_leaves_an_unparseable_custom_type_alone(value):
    class Weird:
        def __init__(self, raw):
            raise ValueError("nope")

    assert from_widget(param(type=Weird, default="x"), value) in (value, "x")
