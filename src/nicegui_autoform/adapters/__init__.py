"""Framework adapters and the registry that dispatches between them.

An adapter is any object exposing ``name``, ``matches(target)`` and
``build(target, command)``. The bundled ones are modules. Adapters never import
their framework at module scope: :func:`matches` first checks whether the
framework is even in ``sys.modules``, because a caller cannot be holding a
cyclopts ``App`` without cyclopts having been imported.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..spec import CommandSpec
from . import _argparse, _click, _cyclopts, _typer, plain


@runtime_checkable
class Adapter(Protocol):
    """What :func:`register_adapter` accepts."""

    name: str

    def matches(self, target: Any) -> bool: ...

    def build(self, target: Any, command: str | None = None) -> CommandSpec: ...


# Order matters: typer before click, since a Typer app resolves *to* a click
# command; plain last, as the catch-all for dataclasses and bare functions.
_ADAPTERS: list[Any] = [_cyclopts, _typer, _click, _argparse, plain]


def register_adapter(adapter: Any, *, first: bool = True) -> None:
    """Add a custom adapter. Registered first by default, so it can take
    precedence over a bundled one."""
    for attr in ("name", "matches", "build"):
        if not hasattr(adapter, attr):
            raise TypeError(f"adapter is missing required attribute {attr!r}")
    _ADAPTERS.insert(0, adapter) if first else _ADAPTERS.append(adapter)


def adapters() -> tuple[Any, ...]:
    """The registry, in dispatch order."""
    return tuple(_ADAPTERS)


def build_spec(target: Any, command: str | None = None) -> CommandSpec:
    """Introspect *target* into a :class:`~nicegui_autoform.spec.CommandSpec`."""
    for adapter in _ADAPTERS:
        if adapter.matches(target):
            return adapter.build(target, command)
    raise TypeError(
        f"no adapter can handle {target!r} (type {type(target).__name__}). "
        "Expected a cyclopts App, click Command, Typer app, ArgumentParser, "
        "dataclass or annotated function."
    )


__all__ = ["Adapter", "adapters", "build_spec", "register_adapter"]
