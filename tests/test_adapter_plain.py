"""The framework-free adapter: bare dataclasses and annotated functions."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

import cyclopts
import pytest

from nicegui_autoform import MISSING, ExcludeFromAutoform, build_spec


class Mode(enum.StrEnum):
    fast = "fast"
    slow = "slow"


@dataclass
class Settings:
    """A documented dataclass."""

    data: Path
    epochs: int = 10
    mode: Mode = Mode.fast
    tags: list[str] = field(default_factory=list)


def test_dataclass_fields_become_params():
    spec = build_spec(Settings)
    assert [p.name for p in spec.params] == ["data", "epochs", "mode", "tags"]
    assert spec.get("data").required and spec.get("data").default is MISSING
    assert spec.get("epochs").default == 10
    assert spec.get("mode").choices == ("fast", "slow")
    assert spec.get("tags").multiple and spec.get("tags").default == []


def test_the_dataclass_itself_is_the_callback():
    spec = build_spec(Settings)
    args, kwargs = spec.bind({("data",): Path("/tmp/x"), ("epochs",): 3})
    assert spec.callback is not None
    assert spec.callback(*args, **kwargs) == Settings(data=Path("/tmp/x"), epochs=3)


def test_authored_docstring_is_kept_but_the_synthesised_one_is_not():
    @dataclass
    class Undocumented:
        x: int = 1

    assert build_spec(Settings).help == "A documented dataclass."
    assert build_spec(Undocumented).help is None


def test_annotated_exclude_marker_hides_a_field():
    @dataclass
    class WithHidden:
        visible: int = 1
        secret: Annotated[int, ExcludeFromAutoform] = 2

    spec = build_spec(WithHidden)
    assert spec.get("secret").hidden
    assert [p.name for p in spec.visible_params()] == ["visible"]


def test_field_metadata_escape_hatch_hides_a_field():
    @dataclass
    class WithHidden:
        visible: int = 1
        secret: int = field(default=2, metadata={"autoform_exclude": True})

    assert build_spec(WithHidden).get("secret").hidden


def test_non_init_fields_are_skipped():
    @dataclass
    class WithDerived:
        x: int = 1
        derived: int = field(default=0, init=False)

    assert [p.name for p in build_spec(WithDerived).params] == ["x"]


def test_cyclopts_parameter_help_is_still_read_from_annotations():
    # The original autoform's one cyclopts dependency, preserved.
    @dataclass
    class Documented:
        x: Annotated[int, cyclopts.Parameter(help="the x value")] = 1

    assert build_spec(Documented).get("x").help == "the x value"


def test_a_later_parameter_annotation_overrides_an_earlier_one():
    @dataclass
    class Documented:
        x: Annotated[
            int, cyclopts.Parameter(help="first"), cyclopts.Parameter(help="second")
        ] = 1

    assert build_spec(Documented).get("x").help == "second"


def test_a_plain_function_works_without_any_cli_framework():
    def train(data: Path, epochs: int = 10, verbose: bool = False):
        """Train a model."""

    spec = build_spec(train)
    assert spec.help == "Train a model."
    assert [p.name for p in spec.params] == ["data", "epochs", "verbose"]
    assert spec.get("verbose").is_flag
    assert spec.callback is train


def test_var_args_are_skipped():
    def train(x: int = 1, *args, **kwargs): ...

    assert [p.name for p in build_spec(train).params] == ["x"]


def test_positional_only_function_params_are_marked():
    def train(a: int, /, b: int = 2): ...

    assert build_spec(train).get("a").positional_only


def test_command_is_rejected_since_there_are_no_subcommands():
    with pytest.raises(ValueError, match="no subcommands"):
        build_spec(Settings, "train")


def test_an_unsupported_target_names_what_is_expected():
    with pytest.raises(TypeError, match="no adapter can handle"):
        build_spec(42)
