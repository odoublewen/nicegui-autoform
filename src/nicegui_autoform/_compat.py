"""Version shims for the optional CLI frameworks."""

from __future__ import annotations

from typing import Any

from .spec import MISSING

#: Params Typer injects into every app unless ``add_completion=False``.
TYPER_INJECTED_PARAMS = frozenset({"install_completion", "show_completion"})


def click_default(param: Any) -> Any:
    """A click parameter's declared default, normalised to :data:`MISSING`.

    Read straight off ``param.default`` rather than through
    ``param.get_default(ctx)``: Typer subclasses its own vendored copy of click,
    so a ``click.Context`` built from the installed click is not the context a
    ``TyperOption`` expects, and on some click versions the mismatch silently
    yields UNSET for a parameter that plainly has a default.

    click 8.3 reports an unset default as ``Sentinel.UNSET`` where older
    versions report ``None``. ``None`` is a legal default, so the two stay
    distinguishable wherever click gives us enough to tell them apart.
    """
    default = getattr(param, "default", None)
    if callable(default):
        # click allows a zero-argument callable as a default.
        try:
            default = default()
        except Exception:
            return MISSING
    return MISSING if _is_click_unset(default) else default


def _is_click_unset(value: Any) -> bool:
    if value is None:
        return False
    sentinel = _click_unset_sentinel()
    if sentinel is not None and value is sentinel:
        return True
    # Fall back to a structural check so an unknown click release still works.
    return type(value).__name__ == "Sentinel" and repr(value) == "Sentinel.UNSET"


def _click_unset_sentinel() -> Any:
    try:
        from click import core
    except ImportError:  # pragma: no cover - click is an optional extra
        return None
    return getattr(core, "UNSET", None)
