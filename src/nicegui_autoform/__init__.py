"""Render a NiceGUI web form from a command line interface.

Point :class:`AutoForm` at a CLI you already have -- a cyclopts ``App``, a click
``Command``, a ``typer.Typer``, an ``argparse.ArgumentParser``, or a plain
dataclass or annotated function -- and it builds a form from that CLI's own
parameter metadata and calls the same function on submit.

    from nicegui import ui
    from nicegui_autoform import AutoForm

    AutoForm(app, command="train")
    ui.run()
"""

from .adapters import Adapter, adapters, build_spec, register_adapter
from .form import AutoForm
from .spec import (
    MISSING,
    CommandSpec,
    ContainerSpec,
    ExcludeFromAutoform,
    ParamSpec,
    WidgetKind,
)
from .validate import collect_errors
from .values import from_widget, to_widget
from .widgets import choose_widget

__version__ = "0.1.0"

__all__ = [
    "MISSING",
    "Adapter",
    "AutoForm",
    "CommandSpec",
    "ContainerSpec",
    "ExcludeFromAutoform",
    "ParamSpec",
    "WidgetKind",
    "__version__",
    "adapters",
    "build_spec",
    "choose_widget",
    "collect_errors",
    "from_widget",
    "register_adapter",
    "to_widget",
]
