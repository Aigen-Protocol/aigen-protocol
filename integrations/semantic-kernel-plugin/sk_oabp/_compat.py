"""Optional-dependency shim for Semantic Kernel (``semantic-kernel``).

The whole point of this integration is to expose OABP marketplace operations as
``@kernel_function``-decorated methods on a `Semantic Kernel
<https://learn.microsoft.com/en-us/semantic-kernel/>`_ native plugin class, so a
``Kernel`` (and its function-calling chat completion / planners) can call them.
But the spec also requires the package to remain **importable when
``semantic-kernel`` is not installed**, with the decorated methods staying
ordinary, directly-callable Python methods.

This module is the single seam that makes both true:

* When ``semantic_kernel`` is importable we re-export the real
  :func:`semantic_kernel.functions.kernel_function` and set :data:`HAS_SK` to
  ``True``.
* Otherwise we provide a drop-in :func:`kernel_function` that returns the wrapped
  function **unchanged** (a no-op decorator) — so every ``OabpPlugin`` method
  stays a normal callable you can invoke directly — while still attaching the
  ``name`` / ``description`` metadata the real SK decorator records, under the
  same ``__kernel_function__`` marker plus convenience aliases. Importing the
  package, constructing :class:`OabpPlugin`, and calling its methods all keep
  working with no Semantic Kernel installed.

Every other module imports these names from here, never from ``semantic_kernel``
directly, so the presence/absence decision lives in exactly one place.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

__all__ = [
    "HAS_SK",
    "SK_IMPORT_ERROR",
    "kernel_function",
    "require_semantic_kernel",
]


def _make_fallback_kernel_function() -> Callable[..., Any]:
    """Build the no-Semantic-Kernel fallback ``@kernel_function`` decorator.

    Returns a decorator that hands the function back **unchanged** (so the
    plugin methods remain directly callable), after recording the ``name`` /
    ``description`` metadata the real Semantic Kernel decorator would attach.
    Both call styles are supported — bare ``@kernel_function`` and parametrised
    ``@kernel_function(name=..., description=...)``.
    """

    def kernel_function(
        func: Optional[Callable[..., Any]] = None,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        **_kwargs: Any,
    ) -> Any:
        def _decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
            resolved_name = name or getattr(fn, "__name__", "function")
            resolved_desc = (
                description
                or (fn.__doc__ or "").strip().split("\n\n")[0].strip()
            )
            # Mirror the metadata real Semantic Kernel records on the function so
            # callers/tests can introspect it identically in both worlds.
            fn.__kernel_function__ = True  # type: ignore[attr-defined]
            fn.__kernel_function_name__ = resolved_name  # type: ignore[attr-defined]
            fn.__kernel_function_description__ = resolved_desc  # type: ignore[attr-defined]
            # Convenience aliases used by this package's helpers when SK is absent.
            fn.oabp_function_name = resolved_name  # type: ignore[attr-defined]
            fn.oabp_function_description = resolved_desc  # type: ignore[attr-defined]
            fn.is_oabp_fallback_function = True  # type: ignore[attr-defined]
            return fn

        # Parametrised form: @kernel_function(name=..., description=...).
        if func is None:
            return _decorate
        # Bare form: @kernel_function.
        return _decorate(func)

    return kernel_function


try:
    from semantic_kernel.functions import kernel_function  # type: ignore

    HAS_SK = True
    SK_IMPORT_ERROR: Optional[BaseException] = None

    def require_semantic_kernel(feature: str = "this feature") -> None:  # noqa: D401
        """No-op when ``semantic-kernel`` is installed."""
        return None

except Exception as _exc:  # pragma: no cover - depends on env
    HAS_SK = False
    SK_IMPORT_ERROR = _exc

    kernel_function = _make_fallback_kernel_function()

    def require_semantic_kernel(feature: str = "this feature") -> None:
        raise RuntimeError(
            f"{feature} requires the 'semantic-kernel' package, which is not "
            "installed. Install it with `pip install semantic-kernel` (or "
            "`pip install \"sk-oabp[semantic-kernel]\"`). The OabpPlugin methods "
            "themselves still work as plain callables without it."
        )
