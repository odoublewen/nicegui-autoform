"""Form-side validation, standing in for the CLI parser we bypass."""

from __future__ import annotations

from nicegui_autoform import MISSING, ParamSpec, collect_errors
from nicegui_autoform.validate import NOT_A_NUMBER, NOT_AN_INTEGER, REQUIRED, check


def param(**kwargs) -> ParamSpec:
    kwargs.setdefault("name", "p")
    kwargs.setdefault("path", ("p",))
    kwargs.setdefault("cli_name", "--p")
    return ParamSpec(**kwargs)


def test_required_field_left_empty():
    assert check(param(required=True), "") == REQUIRED
    assert check(param(required=True), None) == REQUIRED
    assert check(param(required=True), MISSING) == REQUIRED


def test_optional_field_left_empty_is_fine():
    assert check(param(required=False), "") is None


def test_whitespace_does_not_satisfy_a_required_field():
    assert check(param(required=True), "   ") == REQUIRED


def test_a_flag_is_never_required():
    assert check(param(type=bool, is_flag=True, required=True), False) is None


def test_int_field_rejects_a_fraction():
    assert check(param(type=int), 1.5) == NOT_AN_INTEGER
    assert check(param(type=int), 2.0) is None


def test_number_field_rejects_text():
    assert check(param(type=float), "abc") == NOT_A_NUMBER


def test_range_bounds_are_enforced():
    p = param(type=int, minimum=1, maximum=64)
    assert check(p, 0) == "Must be at least 1"
    assert check(p, 65) == "Must be at most 64"
    assert check(p, 32) is None


def test_float_bounds_keep_their_decimals():
    assert check(param(type=float, maximum=0.5), 0.9) == "Must be at most 0.5"


def test_value_outside_choices_is_rejected():
    p = param(choices=("fast", "slow"))
    assert check(p, "medium") == "Must be one of: fast, slow"
    assert check(p, "fast") is None


def test_required_multiple_needs_at_least_one_value():
    assert check(param(multiple=True, required=True), []) == REQUIRED
    assert check(param(multiple=True, required=True), ["a"]) is None
    assert check(param(multiple=True, required=False), []) is None


def test_every_element_of_a_multiple_is_checked():
    p = param(type=int, multiple=True)
    assert check(p, [1, "x"]) == NOT_A_NUMBER


def test_collect_errors_is_keyed_by_path():
    params = [
        param(name="a", path=("a",), required=True),
        param(name="b", path=("cfg", "b"), type=int),
        param(name="c", path=("c",)),
    ]
    errors = collect_errors(params, {("a",): "", ("cfg", "b"): 1.5, ("c",): "ok"})
    assert errors == {("a",): REQUIRED, ("cfg", "b"): NOT_AN_INTEGER}
