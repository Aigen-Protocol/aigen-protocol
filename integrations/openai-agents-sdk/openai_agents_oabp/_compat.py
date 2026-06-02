"""Optional-dependency shim for the OpenAI Agents SDK (``openai-agents``).

The whole point of this integration is to expose OABP marketplace operations as
``@function_tool``-decorated tools for the `openai-agents
<https://openai.github.io/openai-agents-python/>`_ SDK, and to build a ready-made
:class:`agents.Agent`. But the spec also requires the package to remain
**importable when ``openai-agents`` is not installed**, with the tools degrading
to *plain callables*.

This module is the single seam that makes both true:

* When ``agents`` is importable we re-export the real
  :func:`agents.function_tool`, :class:`agents.FunctionTool`,
  :class:`agents.Agent` and :class:`agents.Runner`, and set
  :data:`HAS_AGENTS` to ``True``.
* Otherwise we provide a drop-in :func:`function_tool` that returns the wrapped
  Python function **unchanged** (so ``oabp_list_missions`` et al. are still
  ordinary callables you can invoke directly), plus lightweight ``Agent`` /
  ``Runner`` / ``FunctionTool`` placeholders that raise a clear, actionable
  error only *if* you actually try to use the agent-runtime pieces. Importing
  the package, building the tool callables, and calling them all keep working.

Every other module imports these names from here, never from ``agents``
directly, so the presence/absence decision lives in exactly one place.
"""

from __future__ import annotations

import functools
from typing import Any, Callable, Optional

__all__ = [
    "HAS_AGENTS",
    "AGENTS_IMPORT_ERROR",
    "function_tool",
    "FunctionTool",
    "Agent",
    "Runner",
    "require_agents",
]


def _make_fallbacks():
    """Build the no-``agents`` fallbacks. Returns the public symbols."""

    class _MissingAgentsDependency(RuntimeError):
        """Raised when an agent-runtime feature is used without ``openai-agents``."""

    def require_agents(feature: str = "this feature") -> None:
        raise _MissingAgentsDependency(
            f"{feature} requires the 'openai-agents' package, which is not "
            "installed. Install it with `pip install openai-agents` (or "
            "`pip install \"openai-agents-oabp[agents]\"`). The OABP tools "
            "themselves still work as plain callables without it."
        )

    def function_tool(
        func: Optional[Callable[..., Any]] = None,
        *,
        name_override: Optional[str] = None,
        description_override: Optional[str] = None,
        **_kwargs: Any,
    ) -> Any:
        """Fallback ``@function_tool``: return the function as a plain callable.

        Mirrors the real decorator's two call styles — bare ``@function_tool``
        and parametrised ``@function_tool(name_override=...)`` — but, with
        ``openai-agents`` absent, it simply hands back the underlying function
        (annotated with the metadata the real SDK would have read) so it remains
        directly callable. This satisfies the "tools degrade to plain callables"
        contract.
        """

        def _decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
            # Attach the metadata the real FunctionTool would expose, so callers
            # / tests can still introspect name + description off the callable.
            fn.oabp_tool_name = name_override or getattr(fn, "__name__", "tool")  # type: ignore[attr-defined]
            fn.oabp_tool_description = (  # type: ignore[attr-defined]
                description_override
                or (fn.__doc__ or "").strip().split("\n\n")[0].strip()
            )
            fn.is_oabp_fallback_tool = True  # type: ignore[attr-defined]
            return fn

        # Parametrised form: @function_tool(...). Return the real decorator.
        if func is None:
            return _decorate
        # Bare form: @function_tool. Decorate immediately.
        return _decorate(func)

    class FunctionTool:  # noqa: D401 - placeholder
        """Placeholder for :class:`agents.FunctionTool` (``openai-agents`` absent)."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            require_agents("agents.FunctionTool")

    class Agent:  # noqa: D401 - placeholder
        """Placeholder for :class:`agents.Agent` (``openai-agents`` absent)."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            require_agents("agents.Agent")

    class Runner:  # noqa: D401 - placeholder
        """Placeholder for :class:`agents.Runner` (``openai-agents`` absent)."""

        @staticmethod
        def run(*args: Any, **kwargs: Any) -> Any:
            require_agents("agents.Runner.run")

        @staticmethod
        def run_sync(*args: Any, **kwargs: Any) -> Any:
            require_agents("agents.Runner.run_sync")

    return function_tool, FunctionTool, Agent, Runner, require_agents


try:
    from agents import Agent, FunctionTool, Runner, function_tool  # type: ignore

    HAS_AGENTS = True
    AGENTS_IMPORT_ERROR: Optional[BaseException] = None

    def require_agents(feature: str = "this feature") -> None:  # noqa: D401
        """No-op when ``openai-agents`` is installed."""
        return None

except Exception as _exc:  # pragma: no cover - depends on env
    HAS_AGENTS = False
    AGENTS_IMPORT_ERROR = _exc
    (
        function_tool,
        FunctionTool,
        Agent,
        Runner,
        require_agents,
    ) = _make_fallbacks()


# Keep a reference so type-checkers / linters don't flag the unused import path.
functools  # noqa: B018
