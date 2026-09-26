"""``AutoForm`` -- the NiceGUI element that renders a command as a web form."""

from __future__ import annotations

import argparse
import inspect
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import is_dataclass
from typing import Any

from nicegui import ui

from . import widgets as _widgets
from .adapters import build_spec
from .spec import MISSING, CommandSpec, ParamSpec, WidgetKind
from .validate import collect_errors
from .values import from_widget, to_widget

# Inspired by (but not copied from)
# https://github.com/Dronakurl/nicecrud and https://github.com/atollk/NiceGooey


class AutoForm:
    """Render a CLI command as a form, and call its function on submit.

    ``target`` may be a cyclopts ``App``, a click ``Command`` or ``Group``, a
    ``typer.Typer``, an ``argparse.ArgumentParser``, a ``@dataclass`` or a plain
    annotated function. ``command`` names which subcommand to render, and is
    required when the target exposes more than one.

    On submit the values are validated against the spec and the command's own
    function is called directly. Pass ``on_submit`` to intercept that; it may be
    sync or async. An ``ArgumentParser`` has no function to call, so it requires
    ``on_submit`` and hands it an ``argparse.Namespace``.
    """

    def __init__(
        self,
        target: Any,
        *,
        command: str | None = None,
        initial: Mapping[str, Any] | Any | None = None,
        exclude: Iterable[str] = (),
        on_submit: Callable[..., None | Awaitable[None]] | None = None,
        widgets: Mapping[str, WidgetKind] | None = None,
        render_submit_button: bool = True,
        submit_label: str = "Submit",
        show_help: bool = True,
        max_file_size: int | None = None,
    ) -> None:
        self.spec: CommandSpec = build_spec(target, command).with_widgets(widgets or {})
        self.exclude = frozenset(exclude)
        self.on_submit = on_submit
        self.render_submit_button = render_submit_button
        self.submit_label = submit_label
        self.show_help = show_help
        self.max_file_size = (
            _widgets.DEFAULT_MAX_FILE_SIZE if max_file_size is None else max_file_size
        )

        if self.spec.callback is None and on_submit is None:
            raise ValueError(
                f"a {self.spec.source} target has no function to call, so on_submit is required; "
                "it will receive an argparse.Namespace"
            )

        #: Live widget values, keyed by dotted parameter path.
        self.values: dict[str, Any] = {}
        #: The ``(args, kwargs)`` of the most recent successful submission.
        self.result: tuple[tuple[Any, ...], dict[str, Any]] | None = None

        self.inputs: dict[str, Any] = {}
        self.error_labels: dict[str, ui.label] = {}

        self._init_values(initial)
        self._build_ui()

        with ui.element("div").classes(
            "fixed inset-0 z-50 flex items-center justify-center bg-black/20"
        ).set_visibility(False) as self.spinner:
            ui.spinner(size="lg", color="primary")

    # ------------------------------------------------------------------ setup

    def visible_params(self) -> tuple[ParamSpec, ...]:
        return self.spec.visible_params(self.exclude)

    def _init_values(self, initial: Mapping[str, Any] | Any | None) -> None:
        supplied = _as_mapping(initial)
        visible = {key(p) for p in self.visible_params()}

        for param in self.spec.params:
            path_key = key(param)
            if path_key in supplied:
                value = supplied[path_key]
            elif param.name in supplied:
                value = supplied[param.name]
            elif param.has_default:
                value = param.default
            elif path_key in visible:
                value = MISSING
            else:
                raise ValueError(
                    f"{param.cli_name} is hidden or excluded but has no default; "
                    f"supply it via initial={{{param.name!r}: ...}}"
                )
            self.values[path_key] = to_widget(param, value)

    def _sections(self) -> list[tuple[str | None, list[ParamSpec]]]:
        """Visible params grouped by section, in first-appearance order."""
        grouped: dict[str | None, list[ParamSpec]] = {}
        for param in self.visible_params():
            grouped.setdefault(param.section, []).append(param)
        return list(grouped.items())

    # --------------------------------------------------------------- building

    def _build_ui(self) -> None:
        with ui.card().classes("w-full p-4 gap-1"):
            if self.show_help and self.spec.help:
                ui.label(self.spec.help).classes("text-base font-medium")

            for section, params in self._sections():
                if section is None:
                    for param in params:
                        self._build_field(param)
                else:
                    with ui.column().classes("w-full gap-1 rounded border p-3 my-2"):
                        ui.label(section).classes("text-sm font-medium text-grey-8")
                        for param in params:
                            self._build_field(param)

            if self.render_submit_button:
                ui.button(self.submit_label, on_click=self.validate_and_submit)

    def _build_field(self, param: ParamSpec) -> None:
        path_key = key(param)
        kind = _widgets.choose_widget(param)
        element, error_label = _widgets.build(
            param,
            kind,
            self.values,
            path_key,
            on_change=lambda name=path_key: self._clear_error(name),
            max_file_size=self.max_file_size,
        )
        self.inputs[path_key] = element
        if error_label is not None:
            self.error_labels[path_key] = error_label

    # -------------------------------------------------------------- submitting

    def python_values(self) -> dict[tuple[str, ...], Any]:
        """Current form values converted to what the callback expects."""
        return {p.path: from_widget(p, self.values.get(key(p))) for p in self.spec.params}

    def errors(self) -> dict[tuple[str, ...], str]:
        """Validation errors for the visible fields, keyed by parameter path."""
        return collect_errors(
            self.visible_params(),
            {p.path: self.values.get(key(p)) for p in self.spec.params},
        )

    async def validate_and_submit(self) -> None:
        self._clear_errors()

        errors = self.errors()
        if errors:
            self._show_errors(errors)
            count = len(errors)
            noun = "field needs" if count == 1 else "fields need"
            ui.notify(f"{count} {noun} attention", type="negative")
            return

        try:
            args, kwargs = self.spec.bind(self.python_values())
        except (TypeError, ValueError) as exc:
            ui.notify(f"Invalid input: {exc}", type="negative")
            return

        self.result = (args, kwargs)
        await self._invoke(args, kwargs)

    async def _invoke(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        handler = self.on_submit or self.spec.callback
        if handler is None:  # guarded in __init__; here for type narrowing
            return

        self.spinner.set_visibility(True)
        try:
            if self.spec.source == "argparse":
                outcome = handler(argparse.Namespace(**kwargs))
            else:
                outcome = handler(*args, **kwargs)
            if inspect.isawaitable(outcome):
                await outcome
        except Exception as exc:  # surfaced in the UI rather than the server log
            ui.notification(
                f"Submission failed: {exc}", type="negative", close_button=True, timeout=None
            )
        finally:
            self.spinner.set_visibility(False)

    # ------------------------------------------------------------ error display

    def _clear_error(self, path_key: str) -> None:
        element = self.inputs.get(path_key)
        if path_key in self.error_labels:
            self.error_labels[path_key].set_visibility(False)
            if element is not None:
                element.props(remove="color")
        elif element is not None:
            element.props(remove="error error-message")

    def _clear_errors(self) -> None:
        for path_key in self.inputs:
            self._clear_error(path_key)

    def _show_errors(self, errors: Mapping[tuple[str, ...], str]) -> None:
        for path, message in errors.items():
            path_key = ".".join(path)
            element = self.inputs.get(path_key)
            if path_key in self.error_labels:
                self.error_labels[path_key].set_text(message)
                self.error_labels[path_key].set_visibility(True)
                if element is not None:
                    element.props["color"] = "negative"
                    element.update()
            elif element is not None:
                element.props["error"] = True
                element.props["error-message"] = message
                element.update()


def key(param: ParamSpec) -> str:
    """The dotted string used to key widget values and elements."""
    return ".".join(param.path)


def _as_mapping(initial: Mapping[str, Any] | Any | None) -> Mapping[str, Any]:
    if initial is None:
        return {}
    if isinstance(initial, Mapping):
        return initial
    if is_dataclass(initial) and not isinstance(initial, type):
        from dataclasses import fields

        return {f.name: getattr(initial, f.name) for f in fields(initial)}
    raise TypeError("initial must be a mapping or a dataclass instance")
