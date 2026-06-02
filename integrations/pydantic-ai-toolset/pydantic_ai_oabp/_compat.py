"""Optional-dependency shim for Pydantic-AI (``pydantic-ai``).

The point of this integration is to expose OABP marketplace operations as
`pydantic-ai <https://ai.pydantic.dev/>`_ ``@agent.tool`` functions and to build
a ready-made :class:`pydantic_ai.Agent`. But the spec requires the package to
remain **importable when ``pydantic-ai`` is not installed**, with tool
*registration* guarded behind a lazy import.

This module is the single seam that makes both true:

* :func:`require_pydantic_ai` raises a clear, actionable error if an
  agent-runtime feature is used without the package.
* :func:`load_pydantic_ai` performs the *lazy* import (only when an
  :class:`~pydantic_ai_oabp.toolset.OabpToolset` is actually registered onto an
  agent, or :func:`~pydantic_ai_oabp.agent.build_agent` is called) and returns
  the ``pydantic_ai`` module. Importing :mod:`pydantic_ai_oabp` itself never
  triggers it.
* :data:`HAS_PYDANTIC_AI` lets callers branch without importing the package.
* :class:`RunContext` is re-exported when available, else a tiny structural
  stand-in is provided so the tool *functions* can be type-annotated and unit
  tested against a fake context with no ``pydantic-ai`` installed.

Every other module imports these names from here, never from ``pydantic_ai``
directly, so the presence/absence decision lives in exactly one place.
"""

from __future__ import annotations

import importlib
from typing import Any, Generic, Optional, TypeVar

__all__ = [
    "HAS_PYDANTIC_AI",
    "PYDANTIC_AI_IMPORT_ERROR",
    "RunContext",
    "load_pydantic_ai",
    "require_pydantic_ai",
]

T = TypeVar("T")


class MissingPydanticAIDependency(RuntimeError):
    """Raised when a Pydantic-AI runtime feature is used without ``pydantic-ai``."""


_INSTALL_HINT = (
    "requires the 'pydantic-ai' package, which is not installed. Install it "
    "with `pip install pydantic-ai` (or `pip install \"pydantic-ai-oabp"
    "[pydantic-ai]\"`). The OABP toolset functions themselves still work as "
    "plain callables (against a RunContext-shaped object) without it."
)


def require_pydantic_ai(feature: str = "this feature") -> None:
    """Raise unless ``pydantic-ai`` is importable. No-op when it is."""
    if not HAS_PYDANTIC_AI:
        raise MissingPydanticAIDependency(f"{feature} {_INSTALL_HINT}")


def load_pydantic_ai():
    """Lazily import and return the ``pydantic_ai`` module.

    This is the *only* place the integration imports ``pydantic_ai``. It is
    called when a toolset is registered onto an agent or an agent is built — not
    at package import time — which is what keeps ``import pydantic_ai_oabp``
    working with the dependency absent.
    """
    require_pydantic_ai("Registering the OABP toolset / building an OABP agent")
    return importlib.import_module("pydantic_ai")


# --------------------------------------------------------------------------- #
# RunContext: re-export the real one, else a minimal structural stand-in.
# --------------------------------------------------------------------------- #
try:  # pragma: no cover - depends on the environment
    import pydantic_ai as _pydantic_ai  # noqa: F401
    from pydantic_ai import RunContext  # type: ignore

    HAS_PYDANTIC_AI = True
    PYDANTIC_AI_IMPORT_ERROR: Optional[BaseException] = None

except Exception as _exc:  # pragma: no cover - depends on the environment
    HAS_PYDANTIC_AI = False
    PYDANTIC_AI_IMPORT_ERROR = _exc

    class RunContext(Generic[T]):  # type: ignore[no-redef]
        """Minimal stand-in for :class:`pydantic_ai.RunContext` (dep absent).

        Pydantic-AI injects a ``RunContext[Deps]`` as the first argument of an
        ``@agent.tool`` function; ``ctx.deps`` is your dependencies object. When
        ``pydantic-ai`` is not installed we provide this structurally-compatible
        shim so the OABP tool functions can be:

        * **type-annotated** identically (``ctx: RunContext[OabpDeps]``), and
        * **unit-tested** by constructing ``RunContext(deps=OabpDeps(...))`` and
          calling the tool functions directly — exactly what the offline test
          suite does.

        Only the ``deps`` attribute is modelled; the real class carries much
        more (model, usage, messages, ...), which the tools here do not use.
        """

        def __init__(self, deps: T = None, **extra: Any) -> None:  # type: ignore[assignment]
            self.deps = deps
            # Accept (and expose) any extra kwargs the real RunContext might
            # carry, so a test can pass them without error.
            for key, value in extra.items():
                setattr(self, key, value)

        def __class_getitem__(cls, _item: Any) -> Any:  # noqa: D401
            # Support the subscripted form ``RunContext[OabpDeps]`` in
            # annotations even though this shim ignores the type parameter.
            return cls
