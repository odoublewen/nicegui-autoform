"""Cyclopts, including a nested dataclass rendered as a section.

    uv run python examples/cyclopts_demo.py

    Upload examples/data/measurements.csv into the Data field to submit.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import cyclopts
from nicegui import ui

from nicegui_autoform import AutoForm

app = cyclopts.App(name="trainer")

def summarise(data: Path) -> str:
    """Prove the upload arrived: the callback gets a real, readable file."""
    lines = data.read_text().splitlines()
    return f"{data.name} ({len(lines)} lines, {data.stat().st_size} bytes)"



class Mode(enum.StrEnum):
    fast = "fast"
    slow = "slow"


@dataclass
class Tuning:
    """Tuning.

    Parameters
    ----------
    lr: float
        learning rate
    workers: int
        parallel worker processes
    """

    lr: float = 0.001
    workers: int = 4


DEFAULT_TUNING = Tuning()


@app.command
def train(
    data: Path,
    epochs: int = 10,
    mode: Mode = Mode.fast,
    verbose: Annotated[bool, cyclopts.Parameter(help="log every step")] = False,
    tags: list[str] = [],  # noqa: B006 - cyclopts reads the annotation, not the object
    tuning: Tuning = DEFAULT_TUNING,
):
    """Train a model.

    Parameters
    ----------
    data: Path
        the input data file
    epochs: int
        number of epochs
    mode: Mode
        scheduling mode
    """
    ui.notify(
        f"train(data={summarise(data)}, epochs={epochs}, mode={mode}, "
        f"verbose={verbose}, tags={tags}, tuning={tuning})",
        type="positive",
        multi_line=True,
        close_button=True,
    )


@ui.page("/")
def index() -> None:
    ui.label("cyclopts").classes("text-h5")
    AutoForm(app, command="train")


ui.run(title="cyclopts demo", reload=False)
