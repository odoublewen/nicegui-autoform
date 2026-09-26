"""Argparse specifics: action kinds, groups, subparsers, and no callback."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from nicegui_autoform import MISSING, build_spec


def test_store_true_becomes_a_flag():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    param = build_spec(parser).get("verbose")
    assert param.is_flag and param.type is bool and param.default is False


def test_store_false_is_also_a_flag():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_false")
    assert build_spec(parser).get("quiet").is_flag


def test_append_action_is_multiple():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", dest="tags", action="append", default=[])
    param = build_spec(parser).get("tags")
    assert param.multiple and param.default == []


def test_variadic_nargs_is_multiple():
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", nargs="+", type=Path)
    assert build_spec(parser).get("files").multiple


def test_fixed_nargs_is_multiple_and_records_its_count():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", nargs=2, type=int)
    param = build_spec(parser).get("pair")
    assert param.multiple and param.nargs == 2


def test_positional_is_required():
    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path)
    param = build_spec(parser).get("data")
    assert param.required and param.default is MISSING


def test_optional_positional_is_not_required():
    parser = argparse.ArgumentParser()
    parser.add_argument("data", nargs="?", default="x")
    assert not build_spec(parser).get("data").required


def test_choices_are_captured():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["fast", "slow"], default="fast")
    assert build_spec(parser).get("mode").choices == ("fast", "slow")


def test_filetype_renders_as_a_path():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=argparse.FileType("w"))  # ty: ignore[deprecated]
    assert build_spec(parser).get("out").type is Path


def test_a_lambda_converter_degrades_to_text():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weird", type=lambda s: s.upper())
    assert build_spec(parser).get("weird").type is str


def test_help_and_version_actions_are_skipped():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", action="version", version="1.0")
    parser.add_argument("--x", type=int)
    assert [p.name for p in build_spec(parser).params] == ["x"]


def test_suppressed_arguments_are_skipped():
    parser = argparse.ArgumentParser()
    parser.add_argument("--internal", help=argparse.SUPPRESS)
    parser.add_argument("--x", type=int)
    assert [p.name for p in build_spec(parser).params] == ["x"]


def test_custom_argument_groups_become_sections():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plain", type=int)
    group = parser.add_argument_group("Advanced")
    group.add_argument("--tuned", type=int)
    spec = build_spec(parser)
    assert spec.get("tuned").section == "Advanced"
    assert spec.get("plain").section is None  # argparse's own default groups


def test_subparsers_are_selected_by_command_name():
    parser = argparse.ArgumentParser(prog="demo")
    sub = parser.add_subparsers(dest="cmd")
    run = sub.add_parser("run")
    run.add_argument("--x", type=int, default=1)

    spec = build_spec(parser, "run")
    assert [p.name for p in spec.params] == ["x"]


def test_unknown_subcommand_names_the_available_ones():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    sub.add_parser("run")
    with pytest.raises(KeyError, match="available"):
        build_spec(parser, "nope")


def test_the_subparsers_action_itself_is_not_a_field():
    parser = argparse.ArgumentParser()
    parser.add_argument("--x", type=int)
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("run")
    assert [p.name for p in build_spec(parser).params] == ["x"]


def test_there_is_no_callback_to_call():
    parser = argparse.ArgumentParser()
    parser.add_argument("--x", type=int)
    assert build_spec(parser).callback is None
