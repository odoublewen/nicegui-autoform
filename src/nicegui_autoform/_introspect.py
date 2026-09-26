"""Typing helpers shared by the adapters.

These answer the questions every adapter has to ask of a type hint: what is the
scalar type underneath, is it a collection, what are its choices.
"""

from __future__ import annotations

import enum
import types
from collections.abc import Sequence
from typing import Annotated, Any, Literal, Union, get_args, get_origin

from .spec import ExcludeFromAutoform

_COLLECTION_ORIGINS = (list, set, frozenset, tuple, Sequence)


def unwrap_annotated(hint: Any) -> Any:
    """Strip ``Annotated[...]`` wrappers down to the underlying type."""
    while get_origin(hint) is Annotated:
        hint = get_args(hint)[0]
    return hint


def annotated_metadata(hint: Any) -> tuple[Any, ...]:
    """Every piece of ``Annotated`` metadata, outermost wrapper first."""
    meta: list[Any] = []
    while get_origin(hint) is Annotated:
        meta.extend(hint.__metadata__)
        hint = get_args(hint)[0]
    return tuple(meta)


def has_exclude_marker(hint: Any) -> bool:
    return any(
        m is ExcludeFromAutoform or isinstance(m, ExcludeFromAutoform)
        for m in annotated_metadata(hint)
    )


def strip_optional(hint: Any) -> Any:
    """Reduce ``X | None`` / ``Optional[X]`` to ``X``.

    A union of several real types reduces to its first member, which is what the
    original autoform did and what a single form field can meaningfully offer.
    """
    if get_origin(hint) in (Union, types.UnionType):
        args = [a for a in get_args(hint) if a is not type(None)]
        if args:
            return args[0]
    return hint


def is_collection(hint: Any) -> bool:
    """True for ``list[str]``, ``tuple[int, ...]``, ``set[str]`` and friends."""
    origin = get_origin(hint)
    if origin is None:
        return hint in _COLLECTION_ORIGINS
    return origin in _COLLECTION_ORIGINS or (
        isinstance(origin, type) and issubclass(origin, _COLLECTION_ORIGINS)
    )


def element_type(hint: Any) -> Any:
    """The element type of a collection hint, or ``str`` if unparameterised."""
    args = [a for a in get_args(hint) if a is not Ellipsis]
    return strip_optional(unwrap_annotated(args[0])) if args else str


def choices_of(hint: Any) -> tuple[str, ...] | None:
    """Choice strings for a ``Literal`` or ``Enum`` hint, else ``None``."""
    hint = strip_optional(unwrap_annotated(hint))
    if get_origin(hint) is Literal:
        return tuple(str(a) for a in get_args(hint))
    if isinstance(hint, type) and issubclass(hint, enum.Enum):
        return tuple(m.name for m in hint)
    return None


def resolve(hint: Any) -> tuple[Any, bool]:
    """Reduce a hint to ``(scalar_type, is_multiple)``.

    ``list[Path]`` becomes ``(Path, True)``; ``str | None`` becomes
    ``(str, False)``. Unresolvable hints fall back to ``str``, which renders as a
    text input rather than failing.
    """
    hint = strip_optional(unwrap_annotated(hint))
    multiple = False
    if is_collection(hint):
        multiple = True
        hint = element_type(hint)
    if get_origin(hint) is Literal:
        # A Literal renders as a choice list; its scalar type is that of its members.
        args = get_args(hint)
        return (type(args[0]) if args else str), multiple
    if hint is Any or hint is None or hint is type(None):
        return str, multiple
    return hint, multiple
