"""The intermediate representation that sits between CLI frameworks and the form.

Adapters in :mod:`nicegui_autoform.adapters` turn a cyclopts ``App``, a click
``Command``, a ``typer.Typer``, an ``argparse.ArgumentParser`` or a plain
dataclass/function into a :class:`CommandSpec`. Everything downstream -- widget
selection, validation, rendering -- only ever sees the spec.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Final


class _Missing:
    """Sentinel for "no value", distinct from ``None`` which is a legal default."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "MISSING"

    def __bool__(self) -> bool:
        return False


#: Compare against this with ``is``. A parameter whose default is ``MISSING``
#: has no default at all; one whose default is ``None`` defaults to ``None``.
MISSING: Final = _Missing()


class WidgetKind(StrEnum):
    """Which NiceGUI element renders a parameter."""

    TEXT = "text"
    TEXTAREA = "textarea"
    PASSWORD = "password"
    INT = "int"
    FLOAT = "float"
    CHECKBOX = "checkbox"
    SELECT = "select"
    MULTISELECT = "multiselect"
    UPLOAD = "upload"
    PATH_TEXT = "path_text"
    CHIPS = "chips"


@dataclass(frozen=True, slots=True)
class ParamSpec:
    """One leaf parameter of a command.

    ``path`` is the parameter's structural identity: ``('epochs',)`` for a
    top-level parameter, ``('config', 'epochs')`` for a field of a nested
    dataclass. It is the key used everywhere -- form values, validation errors,
    binding -- because unlike ``cli_name`` it stays unambiguous when two
    containers are flattened into the same namespace.
    """

    name: str
    path: tuple[str, ...]
    cli_name: str
    annotation: Any = None
    type: Any = str
    required: bool = False
    default: Any = MISSING
    help: str | None = None
    choices: tuple[str, ...] | None = None
    multiple: bool = False
    nargs: int | None = None
    is_flag: bool = False
    negative_cli_name: str | None = None
    hidden: bool = False
    section: str | None = None
    env_var: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    positional_only: bool = False
    widget: WidgetKind | None = None

    @property
    def label(self) -> str:
        """Human-facing field label, e.g. ``'Learning Rate'``."""
        return self.name.replace("_", " ").replace("-", " ").title()

    @property
    def has_default(self) -> bool:
        return self.default is not MISSING


@dataclass(frozen=True, slots=True)
class ContainerSpec:
    """A structural container -- a dataclass whose fields are rendered inline.

    ``factory`` is called with the container's leaf values to rebuild the object
    before the command callback is invoked.
    """

    path: tuple[str, ...]
    factory: Callable[..., Any]
    title: str
    help: str | None = None


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """A single command, flattened to its leaf parameters."""

    name: str
    help: str | None = None
    params: tuple[ParamSpec, ...] = ()
    containers: tuple[ContainerSpec, ...] = ()
    callback: Callable[..., Any] | None = None
    source: str = "plain"
    extras: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        seen: set[tuple[str, ...]] = set()
        for p in self.params:
            if p.path in seen:
                raise ValueError(f"duplicate parameter path {p.path!r} in command {self.name!r}")
            seen.add(p.path)

    def visible_params(self, exclude: frozenset[str] = frozenset()) -> tuple[ParamSpec, ...]:
        """Params to render: neither hidden by the CLI nor excluded by the caller.

        ``exclude`` matches either a bare name (``'epochs'``) or a dotted path
        (``'config.epochs'``).
        """
        return tuple(
            p
            for p in self.params
            if not p.hidden and p.name not in exclude and ".".join(p.path) not in exclude
        )

    def get(self, path: tuple[str, ...] | str) -> ParamSpec:
        """Look a parameter up by path tuple, dotted string, or bare name."""
        if isinstance(path, str):
            path = tuple(path.split("."))
        for p in self.params:
            if p.path == path:
                return p
        if len(path) == 1:
            matches = [p for p in self.params if p.name == path[0]]
            if len(matches) == 1:
                return matches[0]
        raise KeyError(".".join(path))

    def defaults(self) -> dict[tuple[str, ...], Any]:
        """Starting form values: every param's default, or ``MISSING``."""
        return {p.path: p.default for p in self.params}

    def with_widgets(self, widgets: Mapping[str, WidgetKind]) -> CommandSpec:
        """Return a copy with widget overrides applied, keyed by name or dotted path."""
        if not widgets:
            return self
        new = []
        for p in self.params:
            override = widgets.get(".".join(p.path), widgets.get(p.name))
            new.append(replace(p, widget=override) if override is not None else p)
        return replace(self, params=tuple(new))

    def bind(self, values: Mapping[tuple[str, ...], Any]) -> tuple[tuple[Any, ...], dict[str, Any]]:
        """Reassemble form values into ``(args, kwargs)`` for :attr:`callback`.

        Nested containers are rebuilt deepest-first, so a value dict keyed by
        ``('config', 'epochs')`` becomes ``config=Config(epochs=...)``. Values
        that are :data:`MISSING` are dropped entirely, letting the callback's own
        defaults apply.
        """
        resolved: dict[tuple[str, ...], Any] = {
            path: value for path, value in values.items() if value is not MISSING
        }

        for container in sorted(self.containers, key=lambda c: len(c.path), reverse=True):
            depth = len(container.path) + 1
            fields = [p for p in resolved if len(p) == depth and p[:-1] == container.path]
            kwargs = {path[-1]: resolved.pop(path) for path in fields}
            resolved[container.path] = container.factory(**kwargs)

        positional = {p.path[0]: p for p in self.params if p.positional_only and len(p.path) == 1}
        args = tuple(resolved.pop((name,)) for name in positional if (name,) in resolved)
        kwargs = {path[0]: value for path, value in resolved.items() if len(path) == 1}
        return args, kwargs


class ExcludeFromAutoform:
    """Annotation marker: ``Annotated[T, ExcludeFromAutoform]`` hides a field.

    Recognised both as the class itself and as an instance of it.
    """
