"""Click.

uv run python examples/click_demo.py

Upload examples/data/measurements.csv into the Data field to submit.
"""

from __future__ import annotations

from pathlib import Path

import click
from nicegui import ui

from nicegui_autoform import AutoForm


def summarise(data: Path) -> str:
    """Prove the upload arrived: the callback gets a real, readable file."""
    lines = data.read_text().splitlines()
    return f"{data.name} ({len(lines)} lines, {data.stat().st_size} bytes)"


@click.command("train")
@click.argument("data", type=click.Path(path_type=Path))
@click.option("--epochs", type=int, default=10, help="number of epochs")
@click.option("--workers", type=click.IntRange(1, 64), default=4, help="parallel workers")
@click.option("--mode", type=click.Choice(["fast", "slow"]), default="fast")
@click.option("--verbose/--no-verbose", default=False, help="log every step")
@click.option("--tag", "tags", multiple=True, help="repeatable label")
def train(data, epochs, workers, mode, verbose, tags):
    """Train a model."""
    ui.notify(
        f"train(data={summarise(data)}, epochs={epochs}, workers={workers}, "
        f"mode={mode}, verbose={verbose}, tags={list(tags)})",
        type="positive",
        multi_line=True,
        close_button=True,
    )


@ui.page("/")
def index() -> None:
    ui.label("click").classes("text-h5")
    AutoForm(train)


ui.run(title="click demo", reload=False)
