# nicegui-autoform

[![tests](https://github.com/odoublewen/nicegui-autoform/actions/workflows/tests.yml/badge.svg)](https://github.com/odoublewen/nicegui-autoform/actions/workflows/tests.yml)

Render a [NiceGUI](https://nicegui.io) web form from a command line interface.

> **Not an official NiceGUI project.** This is an independent community package
> that builds on NiceGUI. It is not affiliated with, maintained by, or endorsed
> by the NiceGUI project or its authors.

If you already have a function wired up as a CLI, `AutoForm` reads that CLI's own
parameter metadata -- types, defaults, help text, choices, flags -- and builds a form
that calls the same function.

```python
from nicegui import ui
from nicegui_autoform import AutoForm

AutoForm(app, command="train")  # a cyclopts App, click Command, Typer app, ...
ui.run()
```

## Supported frameworks

| Framework | Install | Notes |
|---|---|---|
| [cyclopts](https://cyclopts.readthedocs.io) | `nicegui-autoform[cyclopts]` | Including CLIs defined with a `@dataclass` |
| [click](https://click.palletsprojects.com) | `nicegui-autoform[click]` | |
| [Typer](https://typer.tiangolo.com) | `nicegui-autoform[typer]` | |
| `argparse` | built in | No callback exists, so `on_submit` is required |
| Plain `@dataclass` or annotated function | built in | No CLI framework needed |

The core package depends only on NiceGUI. CLI frameworks are optional extras and are
imported lazily, so nothing is imported that you do not already use.

## Install

```bash
uv add "nicegui-autoform[all]"
```

## Supported versions

Python 3.12 through 3.15. The dependency floors below were measured by running
the test suite against each version rather than guessed:

| Dependency | Floor | Why not lower |
|---|---|---|
| NiceGUI | 3.12 | NiceGUI's own `user` test fixture only works from 3.12, so earlier versions cannot be verified end to end |
| cyclopts | 4.0 | 3.x has a different `ArgumentCollection` API |
| click | 8.1 | 8.0 predates the parameter metadata the adapter reads |
| Typer | 0.13 | 0.12 cannot build its commands against current click |

One caveat on click 8.1 and 8.2: they report an option with no default the same
way as `default=None`, so those two cases are indistinguishable. From click 8.3
onwards an unset default is a distinct `UNSET` sentinel and the form can tell
"no default" from "defaults to None".

## How it works

Each framework has an adapter that produces a `CommandSpec` -- a flat list of
`ParamSpec` leaves plus the containers needed to rebuild nested objects. Everything
downstream (widget selection, validation, rendering) works on that spec alone, so all
frameworks get identical behaviour and a new framework only needs a new adapter.

On submit the form validates its values against the spec and then calls the command's
own function directly. It does not shell out or re-parse a command line.

## Usage

### Choosing a command

```python
AutoForm(cyclopts_app, command="train")
AutoForm(typer_app, command="train")
AutoForm(click_group, command="train")
```

A single-command CLI needs no `command=`.

### Overriding the callback

By default the form calls the command's own function. Pass `on_submit` to intercept it:

```python
async def run(*args, **kwargs):
    ui.notify(f"running with {kwargs}")


AutoForm(app, command="train", on_submit=run)
```

`on_submit` may be sync or async. For an `argparse.ArgumentParser` there is no callback
to default to, so `on_submit` is required and receives an `argparse.Namespace`.

### Nested dataclasses

A cyclopts command taking a dataclass renders its fields as a labelled section, and the
dataclass is rebuilt before the callback is called:

```python
@dataclass
class Config:
    """Training configuration.

    Parameters
    ----------
    epochs: int
        number of epochs
    """

    data: Path
    epochs: int = 10


@app.command
def train(config: Config, seed: int = 0): ...
```

Help text comes from the dataclass's own numpydoc docstring, exactly as cyclopts'
`--help` renders it.

### Widgets and exclusions

```python
from nicegui_autoform import WidgetKind

AutoForm(
    app,
    command="train",
    exclude=["debug", "config.seed"],  # bare name or dotted path
    widgets={"notes": WidgetKind.TEXTAREA},
    initial={"epochs": 50},
)
```

`Path` parameters render as a file upload by default. The upload is written to a private
temporary directory under its **original** name, so the callback receives a real, readable
`Path` whose `.name` is the file the user picked -- useful when the function derives an
output name or switches on the extension. Only the basename of the client-supplied filename
is ever used, so an uploaded name cannot escape that directory.

Use `widgets={"out": WidgetKind.PATH_TEXT}` for an output path that should be typed rather
than uploaded.

## Examples

Four runnable demos, one per framework:

```bash
uv run python examples/cyclopts_demo.py    # nested dataclass as a section
uv run python examples/click_demo.py       # IntRange, Choice, repeatable option
uv run python examples/typer_demo.py       # rich_help_panel as a section
uv run python examples/argparse_demo.py    # on_submit receives a Namespace
```

Each has a required `data` upload. `examples/data/measurements.csv` (12 rows of
dose/response data) is there to drop into it, and `examples/data/notes.txt` shows that a
non-CSV extension survives the round trip. On submit each demo reads the uploaded file and
reports its name and line count, so you can see the real file reached the function.

## Development

```bash
uv sync
uv run pytest
uv run ruff check
uv run ruff format
uv run ty check src tests examples
```

To check a dependency floor, run the suite against that exact version:

```bash
uv run --isolated --with "click==8.1.8" pytest
```

## License

MIT
