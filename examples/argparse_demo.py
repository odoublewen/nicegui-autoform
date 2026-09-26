"""Argparse.

A parser has no callback, so ``on_submit`` is required and receives the
``Namespace`` the form assembled.

    uv run python examples/argparse_demo.py

    Upload examples/data/measurements.csv into the Data field to submit.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from nicegui import ui

from nicegui_autoform import AutoForm

parser = argparse.ArgumentParser(prog="train", description="Train a model.")
parser.add_argument("data", type=Path, help="the input data file")
parser.add_argument("--epochs", type=int, default=10, help="number of epochs")
parser.add_argument("--mode", choices=["fast", "slow"], default="fast")
parser.add_argument("--verbose", action="store_true", help="log every step")
parser.add_argument("--tag", dest="tags", action="append", default=[], help="repeatable label")

advanced = parser.add_argument_group("Advanced")
advanced.add_argument("--workers", type=int, default=4, help="parallel workers")
advanced.add_argument("--seed", type=int, default=0)


def run(args: argparse.Namespace) -> None:
    """A parser has no callback of its own, so this receives the Namespace."""
    lines = args.data.read_text().splitlines()
    ui.notify(
        f"{args.data.name} ({len(lines)} lines) with "
        f"epochs={args.epochs}, mode={args.mode}, verbose={args.verbose}, "
        f"tags={args.tags}, workers={args.workers}, seed={args.seed}",
        type="positive",
        multi_line=True,
        close_button=True,
    )


@ui.page("/")
def index() -> None:
    ui.label("argparse").classes("text-h5")
    AutoForm(parser, on_submit=run)


ui.run(title="argparse demo", reload=False)
