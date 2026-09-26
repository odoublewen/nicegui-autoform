"""Choosing and building the NiceGUI element for a parameter.

:func:`choose_widget` is pure -- it maps a :class:`~nicegui_autoform.spec.ParamSpec`
to a :class:`~nicegui_autoform.spec.WidgetKind` and nothing else -- so the
mapping can be tested without a NiceGUI runtime. :data:`BUILDERS` then turns a
kind into an actual element.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable, MutableMapping
from pathlib import Path
from typing import Any

from nicegui import ui

from .spec import ParamSpec, WidgetKind

#: Passed to ``ui.upload``; a form field is not a bulk transfer mechanism.
DEFAULT_MAX_FILE_SIZE = 50 * 1024 * 1024


def choose_widget(param: ParamSpec) -> WidgetKind:
    """Pick the element kind for a parameter.

    An explicit ``param.widget`` always wins; otherwise choices beat everything
    (a bounded set is a select regardless of the underlying type), then flags,
    then paths, then numbers.
    """
    if param.widget is not None:
        return param.widget
    if param.choices:
        return WidgetKind.MULTISELECT if param.multiple else WidgetKind.SELECT
    if param.is_flag or param.type is bool:
        return WidgetKind.CHECKBOX
    if param.type is Path:
        return WidgetKind.UPLOAD
    if param.type is int:
        return WidgetKind.INT
    if param.type is float:
        return WidgetKind.FLOAT
    if param.multiple:
        return WidgetKind.CHIPS
    return WidgetKind.TEXT


def label_for(param: ParamSpec) -> str:
    """The field label, marked with ``*`` when the parameter is required."""
    return f"{param.label} *" if param.required else param.label


def build(
    param: ParamSpec,
    kind: WidgetKind,
    values: MutableMapping[str, Any],
    key: str,
    *,
    on_change: Callable[[], None] | None = None,
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
) -> tuple[Any, ui.label | None]:
    """Build the element for *param*, bound to ``values[key]``.

    Returns the element and, for kinds that cannot display an error through
    Quasar props, a label to write the error into.
    """
    builder = BUILDERS[kind]
    return builder(param, values, key, on_change, max_file_size)


def _text(param: ParamSpec, values, key, on_change, _max_size) -> tuple[Any, None]:
    element = ui.input(label=label_for(param), placeholder=_placeholder(param))
    return _finish(element, param, values, key, on_change), None


def _textarea(param: ParamSpec, values, key, on_change, _max_size) -> tuple[Any, None]:
    element = ui.textarea(label=label_for(param), placeholder=_placeholder(param))
    return _finish(element, param, values, key, on_change), None


def _password(param: ParamSpec, values, key, on_change, _max_size) -> tuple[Any, None]:
    element = ui.input(label=label_for(param), password=True, password_toggle_button=True)
    return _finish(element, param, values, key, on_change), None


def _integer(param: ParamSpec, values, key, on_change, _max_size) -> tuple[Any, None]:
    element = ui.number(
        label=label_for(param),
        format="%d",
        step=1,
        min=param.minimum,
        max=param.maximum,
        placeholder=_placeholder(param),
    )
    return _finish(element, param, values, key, on_change), None


def _decimal(param: ParamSpec, values, key, on_change, _max_size) -> tuple[Any, None]:
    element = ui.number(
        label=label_for(param),
        min=param.minimum,
        max=param.maximum,
        placeholder=_placeholder(param),
    )
    return _finish(element, param, values, key, on_change), None


def _checkbox(param: ParamSpec, values, key, on_change, _max_size) -> tuple[Any, None]:
    element = ui.checkbox(text=param.label).bind_value(values, key)
    if on_change is not None:
        element.on_value_change(lambda _: on_change())
    _tooltip(element, param)
    return element, None


def _select(param: ParamSpec, values, key, on_change, _max_size) -> tuple[Any, None]:
    element = ui.select(
        options=list(param.choices or []),
        label=label_for(param),
        clearable=not param.required,
    )
    return _finish(element, param, values, key, on_change), None


def _multiselect(param: ParamSpec, values, key, on_change, _max_size) -> tuple[Any, None]:
    element = ui.select(
        options=list(param.choices or []),
        label=label_for(param),
        multiple=True,
    ).props("use-chips")
    return _finish(element, param, values, key, on_change), None


def _chips(param: ParamSpec, values, key, on_change, _max_size) -> tuple[Any, None]:
    element = ui.select(
        options=[],
        label=label_for(param),
        multiple=True,
        new_value_mode="add-unique",
    ).props("use-chips hide-dropdown-icon")
    return _finish(element, param, values, key, on_change), None


def _spill_to_disk(filename: str, content: bytes) -> Path:
    """Write uploaded bytes to a private temp directory under their own name.

    A CLI function that takes a path may well care what the file is called --
    to derive an output name, or to switch on the extension -- so the original
    basename is preserved rather than replaced by a random one. Each upload gets
    its own directory, so keeping real names cannot cause collisions.

    ``filename`` comes from the client, so any directory part is stripped: only
    the basename is ever joined onto the temp directory.
    """
    name = Path(filename).name
    if not name or name in (".", ".."):
        name = "upload"
    target = Path(tempfile.mkdtemp(prefix="nicegui-autoform-")) / name
    target.write_bytes(content)
    return target


def _upload(param: ParamSpec, values, key, on_change, max_file_size) -> tuple[Any, ui.label]:
    """A file upload that hands the callback a readable ``Path``."""

    async def handle_upload(event: Any) -> None:
        path = _spill_to_disk(event.file.name, await event.file.read())
        if param.multiple:
            values[key] = [*(values.get(key) or []), path]
        else:
            values[key] = path
        if on_change is not None:
            on_change()

    def handle_removed(_: Any) -> None:
        values[key] = [] if param.multiple else None

    with ui.column().classes("w-full gap-0"):
        element = (
            ui.upload(
                label=label_for(param),
                multiple=param.multiple,
                max_file_size=max_file_size,
                auto_upload=True,
                on_upload=handle_upload,
                on_rejected=lambda _=None: ui.notify(
                    f"File exceeds the {max_file_size // (1024 * 1024)} MB limit",
                    type="negative",
                ),
            )
            .classes("w-full")
            .props("flat bordered")
        )
        element.on("removed", handle_removed)
        if param.help:
            ui.label(param.help).classes("text-caption text-grey-7 px-3")
        error = ui.label().classes("text-negative text-xs px-3")
        error.set_visibility(False)
    return element, error


def _path_text(param: ParamSpec, values, key, on_change, _max_size) -> tuple[Any, None]:
    element = ui.input(label=label_for(param), placeholder=_placeholder(param) or "path")
    return _finish(element, param, values, key, on_change), None


BUILDERS: dict[WidgetKind, Callable[..., tuple[Any, ui.label | None]]] = {
    WidgetKind.TEXT: _text,
    WidgetKind.TEXTAREA: _textarea,
    WidgetKind.PASSWORD: _password,
    WidgetKind.INT: _integer,
    WidgetKind.FLOAT: _decimal,
    WidgetKind.CHECKBOX: _checkbox,
    WidgetKind.SELECT: _select,
    WidgetKind.MULTISELECT: _multiselect,
    WidgetKind.CHIPS: _chips,
    WidgetKind.UPLOAD: _upload,
    WidgetKind.PATH_TEXT: _path_text,
}


def _finish(element: Any, param: ParamSpec, values, key: str, on_change) -> Any:
    element.bind_value(values, key).classes("w-full")
    if on_change is not None:
        element.on_value_change(lambda _: on_change())
    _tooltip(element, param)
    return element


def _tooltip(element: Any, param: ParamSpec) -> None:
    hint = param.help
    if param.env_var:
        env = ", ".join(param.env_var)
        hint = f"{hint} (env: {env})" if hint else f"env: {env}"
    if hint:
        element.tooltip(hint)


def _placeholder(param: ParamSpec) -> str | None:
    if param.required or not param.has_default or param.default in (None, "", [], ()):
        return None
    return f"default: {param.default}"
