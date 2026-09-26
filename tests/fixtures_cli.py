"""One CLI, defined five ways.

Every builder here describes the same command -- a required ``data`` path, an
``epochs`` int with help text, an ``lr`` float, a ``mode`` choice, a ``verbose``
flag and a repeatable ``tags`` option -- in a different framework. The parity
test asserts they all produce the same form; the per-adapter tests then cover
what is genuinely framework-specific.
"""

from __future__ import annotations

import argparse
import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

import click
import cyclopts
import typer

CALLS: list[dict] = []


class Mode(enum.StrEnum):
    fast = "fast"
    slow = "slow"


def record(**kwargs) -> dict:
    CALLS.append(kwargs)
    return kwargs


def build_cyclopts() -> tuple[object, str]:
    app = cyclopts.App(name="demo")

    @app.command
    def train(
        data: Path,
        epochs: int = 10,
        lr: float = 0.001,
        mode: Mode = Mode.fast,
        verbose: bool = False,
        tags: list[str] = [],  # noqa: B006 - cyclopts reads the annotation, not the object
    ):
        """Train a model.

        Parameters
        ----------
        data: Path
            the input data file
        epochs: int
            number of epochs
        verbose: bool
            chatty
        """
        return record(data=data, epochs=epochs, lr=lr, mode=mode, verbose=verbose, tags=tags)

    return app, "train"


def build_cyclopts_dataclass() -> tuple[object, str]:
    app = cyclopts.App(name="demo")

    @app.command
    def train(
        config: Annotated[TrainConfig, cyclopts.Parameter(name="*")],
    ):
        """Train a model."""
        return record(
            data=config.data,
            epochs=config.epochs,
            lr=config.lr,
            mode=config.mode,
            verbose=config.verbose,
            tags=config.tags,
        )

    return app, "train"


@dataclass
class TrainConfig:
    """Training configuration.

    Parameters
    ----------
    data: Path
        the input data file
    epochs: int
        number of epochs
    verbose: bool
        chatty
    """

    data: Path
    epochs: int = 10
    lr: float = 0.001
    mode: Mode = Mode.fast
    verbose: bool = False
    tags: list[str] = field(default_factory=list)


def build_click() -> tuple[object, None]:
    @click.command("train")
    @click.argument("data", type=click.Path(path_type=Path))
    @click.option("--epochs", type=int, default=10, help="number of epochs")
    @click.option("--lr", type=float, default=0.001)
    @click.option("--mode", type=click.Choice(["fast", "slow"]), default="fast")
    @click.option("--verbose/--no-verbose", default=False, help="chatty")
    @click.option("--tag", "tags", multiple=True)
    def train(data, epochs, lr, mode, verbose, tags):
        """Train a model."""
        return record(data=data, epochs=epochs, lr=lr, mode=mode, verbose=verbose, tags=tags)

    return train, None


def build_typer() -> tuple[object, None]:
    app = typer.Typer()

    @app.command("train")
    def train(
        data: Path,
        epochs: Annotated[int, typer.Option(help="number of epochs")] = 10,
        lr: float = 0.001,
        mode: Mode = Mode.fast,
        verbose: Annotated[bool, typer.Option(help="chatty")] = False,
        tags: Annotated[list[str] | None, typer.Option("--tag")] = None,
    ):
        """Train a model."""
        return record(data=data, epochs=epochs, lr=lr, mode=mode, verbose=verbose, tags=tags or [])

    return app, None


def build_argparse() -> tuple[object, None]:
    parser = argparse.ArgumentParser(prog="train", description="Train a model.")
    parser.add_argument("data", type=Path, help="the input data file")
    parser.add_argument("--epochs", type=int, default=10, help="number of epochs")
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--mode", choices=["fast", "slow"], default="fast")
    parser.add_argument("--verbose", action="store_true", help="chatty")
    parser.add_argument("--tag", dest="tags", action="append", default=[])
    return parser, None


#: ``(id, builder)`` pairs for parametrising the parity test.
BUILDERS = [
    ("cyclopts", build_cyclopts),
    ("cyclopts-dataclass", build_cyclopts_dataclass),
    ("click", build_click),
    ("typer", build_typer),
    ("argparse", build_argparse),
]
