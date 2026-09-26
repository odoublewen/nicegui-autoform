"""Typer, with a rich help panel rendered as a section.

uv run python examples/typer_demo.py

Upload examples/data/measurements.csv into the Data field to submit.
"""

from __future__ import annotations

import enum
from pathlib import Path
from typing import Annotated

import typer
from nicegui import ui

from nicegui_autoform import AutoForm

app = typer.Typer()


def summarise(data: Path) -> str:
    """Prove the upload arrived: the callback gets a real, readable file."""
    lines = data.read_text().splitlines()
    return f"{data.name} ({len(lines)} lines, {data.stat().st_size} bytes)"


class Mode(enum.StrEnum):
    fast = "fast"
    slow = "slow"


@app.command("train")
def train(
    data: Path,
    epochs: Annotated[int, typer.Option(help="number of epochs")] = 10,
    mode: Mode = Mode.fast,
    verbose: Annotated[bool, typer.Option(help="log every step")] = False,
    workers: Annotated[int, typer.Option(rich_help_panel="Advanced")] = 4,
    seed: Annotated[int, typer.Option(rich_help_panel="Advanced")] = 0,
):
    """Train a model."""
    ui.notify(
        f"train(data={summarise(data)}, epochs={epochs}, mode={mode}, "
        f"verbose={verbose}, workers={workers}, seed={seed})",
        type="positive",
        multi_line=True,
        close_button=True,
    )


@ui.page("/")
def index() -> None:
    ui.label("typer").classes("text-h5")
    AutoForm(app, command="train")


ui.run(title="typer demo", reload=False)
