"""Click specifics: the UNSET default sentinel, ranges, choices, groups."""

from __future__ import annotations

import enum
from pathlib import Path

import click
import pytest

from nicegui_autoform import MISSING, build_spec


class Mode(enum.StrEnum):
    fast = "fast"
    slow = "slow"


UNSET_IS_DISTINGUISHABLE = hasattr(click.core, "UNSET")


@pytest.mark.skipif(
    not UNSET_IS_DISTINGUISHABLE,
    reason="before click 8.3 an unset default is reported as None, so the "
    "information needed to tell the two apart does not exist",
)
def test_unset_option_default_becomes_missing_not_none():
    # click 8.3 reports an unset default as Sentinel.UNSET; None is a legal
    # default and must stay distinguishable from "no default at all".
    @click.command()
    @click.option("--a")
    @click.option("--b", default=None)
    def cmd(a, b): ...

    spec = build_spec(cmd)
    assert spec.get("a").default is MISSING
    assert spec.get("b").default is None


def test_an_explicit_none_default_is_preserved():
    @click.command()
    @click.option("--b", default=None)
    def cmd(b): ...

    assert build_spec(cmd).get("b").default is None


def test_unset_multiple_option_starts_as_an_empty_list():
    @click.command()
    @click.option("--tag", "tags", multiple=True)
    def cmd(tags): ...

    param = build_spec(cmd).get("tags")
    assert param.multiple and param.default == []


def test_int_range_becomes_bounds():
    @click.command()
    @click.option("--workers", type=click.IntRange(1, 64), default=4)
    def cmd(workers): ...

    param = build_spec(cmd).get("workers")
    assert (param.type, param.minimum, param.maximum) == (int, 1.0, 64.0)


def test_float_range_becomes_bounds():
    @click.command()
    @click.option("--ratio", type=click.FloatRange(0.0, 1.0), default=0.5)
    def cmd(ratio): ...

    param = build_spec(cmd).get("ratio")
    assert (param.type, param.minimum, param.maximum) == (float, 0.0, 1.0)


def test_path_and_file_types_both_render_as_paths():
    @click.command()
    @click.option("--p", type=click.Path())
    @click.option("--f", type=click.File("w"))
    def cmd(p, f): ...

    spec = build_spec(cmd)
    assert spec.get("p").type is Path
    assert spec.get("f").type is Path


def test_boolean_flag_records_its_negative_form():
    @click.command()
    @click.option("--verbose/--no-verbose", default=False)
    def cmd(verbose): ...

    param = build_spec(cmd).get("verbose")
    assert param.is_flag and param.negative_cli_name == "--no-verbose"


def test_required_argument_has_no_default():
    @click.command()
    @click.argument("data", type=click.Path(path_type=Path))
    def cmd(data): ...

    param = build_spec(cmd).get("data")
    assert param.required and param.default is MISSING


def test_hidden_options_are_dropped_entirely():
    @click.command()
    @click.option("--secret", hidden=True)
    @click.option("--shown")
    def cmd(secret, shown): ...

    assert [p.name for p in build_spec(cmd).params] == ["shown"]


def test_envvar_is_captured():
    @click.command()
    @click.option("--token", envvar="MY_TOKEN")
    def cmd(token): ...

    assert build_spec(cmd).get("token").env_var == ("MY_TOKEN",)


def test_multiline_help_is_collapsed_to_one_line():
    @click.command()
    @click.option("--a", help="first line\n    second line")
    def cmd(a): ...

    assert build_spec(cmd).get("a").help == "first line second line"


def test_group_requires_a_command_name_when_ambiguous():
    @click.group()
    def cli(): ...

    @cli.command()
    def one(): ...

    @cli.command()
    def two(): ...

    with pytest.raises(ValueError, match="command= is required"):
        build_spec(cli)
    assert build_spec(cli, "one").name == "one"


def test_group_with_a_single_command_needs_no_name():
    @click.group()
    def cli(): ...

    @cli.command()
    def only(): ...

    assert build_spec(cli).name == "only"


def test_unknown_command_names_the_available_ones():
    @click.group()
    def cli(): ...

    @cli.command()
    def one(): ...

    with pytest.raises(KeyError, match="available"):
        build_spec(cli, "nope")


def test_callback_annotations_recover_types_click_could_not_express():
    @click.command()
    @click.option("--mode", type=click.Choice(["fast", "slow"]), default="fast")
    def cmd(mode: Mode): ...

    param = build_spec(cmd).get("mode")
    assert param.type is Mode
    assert param.choices == ("fast", "slow")


def test_choice_built_from_an_enum_is_labelled_by_value():
    @click.command()
    @click.option("--mode", type=click.Choice(Mode), default="fast")
    def cmd(mode): ...

    assert build_spec(cmd).get("mode").choices == ("fast", "slow")


def test_unresolvable_annotations_fall_back_to_the_click_types():
    # A callback annotated with a locally-scoped class cannot be resolved by
    # get_type_hints under `from __future__ import annotations`. That must
    # degrade to click's own type rather than raising.
    class LocalOnly(enum.StrEnum):
        a = "a"

    @click.command()
    @click.option("--mode", type=click.Choice(["a"]), default="a")
    def cmd(mode: LocalOnly): ...

    param = build_spec(cmd).get("mode")
    assert param.type is str
    assert param.choices == ("a",)
