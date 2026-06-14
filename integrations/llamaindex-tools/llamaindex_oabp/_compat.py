"""Optional-dependency shim for LlamaIndex (``llama-index-core``).

The point of this integration is to expose OABP marketplace operations as
LlamaIndex :class:`~llama_index.core.tools.FunctionTool` objects (built with
``FunctionTool.from_defaults(...)``) and to assemble a ready-made
``ReActAgent`` / ``FunctionCallingAgent``. But the spec also requires the
package to remain **importable when ``llama-index-core`` is not installed**, with
the tools degrading to lightweight, directly-callable ``FunctionTool``-like
objects that still expose ``name`` + ``description`` + ``fn_schema``.

This module is the single seam that makes both true:

* When ``llama_index.core`` is importable we re-export the real
  :class:`FunctionTool`, :class:`ToolMetadata`, :class:`ReActAgent` and
  :class:`FunctionCallingAgent`, and set :data:`HAS_LLAMA_INDEX` to ``True``.
* Otherwise we provide a drop-in :class:`FunctionTool` whose
  :meth:`~FunctionTool.from_defaults` returns a small object that wraps the
  callable, carries ``name`` / ``description`` / ``fn_schema`` (both directly and
  under a ``.metadata`` namespace mirroring LlamaIndex's ``ToolMetadata``), and
  is itself callable — so ``get_tools()`` keeps working with no LlamaIndex
  installed. The agent classes become lightweight placeholders that raise a
  clear, actionable error only *if* you actually try to build an agent.

Every other module imports these names from here, never from
``llama_index.core`` directly, so the presence/absence decision lives in exactly
one place. Whether real or fallback, a tool's name/description/fn_schema can be
read uniformly via :func:`tool_metadata`.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Type

from pydantic import BaseModel

__all__ = [
    "HAS_LLAMA_INDEX",
    "LLAMA_INDEX_IMPORT_ERROR",
    "FunctionTool",
    "ToolMetadata",
    "ReActAgent",
    "FunctionCallingAgent",
    "require_llama_index",
    "tool_metadata",
]


def tool_metadata(tool: Any) -> Any:
    """Return the object carrying a tool's ``name``/``description``/``fn_schema``.

    Works for both the real LlamaIndex :class:`FunctionTool` (where this metadata
    lives under ``tool.metadata``) and the fallback tool (which mirrors the same
    attributes on ``tool.metadata`` too). Callers should read
    ``tool_metadata(tool).name`` etc. so introspection is identical in both
    modes.
    """
    return getattr(tool, "metadata", tool)


def _make_fallbacks():
    """Build the no-``llama-index`` fallbacks. Returns the public symbols."""

    class _MissingLlamaIndexDependency(RuntimeError):
        """Raised when a LlamaIndex feature is used without ``llama-index-core``."""

    def require_llama_index(feature: str = "this feature") -> None:
        raise _MissingLlamaIndexDependency(
            f"{feature} requires the 'llama-index-core' package, which is not "
            "installed. Install it with `pip install llama-index-core` (or "
            "`pip install \"llamaindex-oabp[llama-index]\"`). The OABP tools "
            "themselves still work as plain callables / FunctionTool-likes "
            "without it."
        )

    class ToolMetadata:
        """Lightweight stand-in for ``llama_index.core.tools.ToolMetadata``.

        Holds the three things an LLM needs to call a tool — ``name``,
        ``description`` and a Pydantic ``fn_schema`` — and can emit the OpenAI
        function-calling parameter schema via :meth:`get_parameters_dict`, just
        like the real class.
        """

        def __init__(
            self,
            name: str,
            description: str,
            fn_schema: Optional[Type[BaseModel]] = None,
        ) -> None:
            self.name = name
            self.description = description
            self.fn_schema = fn_schema

        def get_parameters_dict(self) -> Dict[str, Any]:
            """Return the JSON-schema ``parameters`` block for this tool.

            Mirrors LlamaIndex: derive it from the Pydantic ``fn_schema`` and
            strip the bookkeeping keys the function-calling API does not want.
            """
            if self.fn_schema is None:
                return {"type": "object", "properties": {}, "required": []}
            schema = self.fn_schema.model_json_schema()
            parameters = {
                k: v
                for k, v in schema.items()
                if k in ("type", "properties", "required", "definitions", "$defs")
            }
            parameters.setdefault("type", "object")
            parameters.setdefault("properties", {})
            return parameters

        def __repr__(self) -> str:  # pragma: no cover - debugging aid
            return f"ToolMetadata(name={self.name!r})"

    class FunctionTool:
        """Drop-in stand-in for ``llama_index.core.tools.FunctionTool``.

        Built via :meth:`from_defaults`. Wraps a callable and exposes its
        ``name`` / ``description`` / ``fn_schema`` both directly and under
        ``.metadata`` (a :class:`ToolMetadata`), and is itself callable so the
        tool list is usable even without LlamaIndex installed. ``.call(...)`` and
        ``.acall(...)`` mirror the real tool's invocation API and return a
        :class:`ToolOutput`-like wrapper whose ``.raw_output`` is the tool's dict
        result and whose ``str()`` is that result rendered as text.
        """

        is_llamaindex_oabp_fallback = True

        def __init__(
            self,
            fn: Callable[..., Any],
            metadata: "ToolMetadata",
        ) -> None:
            self._fn = fn
            self.metadata = metadata
            # Convenience mirrors so `tool.name` / `tool.description` /
            # `tool.fn_schema` work directly on the fallback object too.
            self.name = metadata.name
            self.description = metadata.description
            self.fn_schema = metadata.fn_schema

        @classmethod
        def from_defaults(
            cls,
            fn: Callable[..., Any],
            *,
            name: Optional[str] = None,
            description: Optional[str] = None,
            fn_schema: Optional[Type[BaseModel]] = None,
            **_kwargs: Any,
        ) -> "FunctionTool":
            resolved_name = name or getattr(fn, "__name__", "tool")
            resolved_desc = description or (fn.__doc__ or "").strip()
            return cls(
                fn,
                ToolMetadata(
                    name=resolved_name,
                    description=resolved_desc,
                    fn_schema=fn_schema,
                ),
            )

        # -- invocation -----------------------------------------------------
        @property
        def fn(self) -> Callable[..., Any]:
            """The wrapped Python callable."""
            return self._fn

        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            """Call the underlying function directly (returns its raw result)."""
            return self._fn(*args, **kwargs)

        def call(self, *args: Any, **kwargs: Any) -> "_ToolOutput":
            """LlamaIndex-style invocation returning a ToolOutput-like wrapper."""
            raw = self._fn(*args, **kwargs)
            return _ToolOutput(content=str(raw), tool_name=self.metadata.name,
                               raw_input={"args": args, "kwargs": kwargs},
                               raw_output=raw)

        async def acall(self, *args: Any, **kwargs: Any) -> "_ToolOutput":
            """Async wrapper over :meth:`call` (the SDK call itself is sync)."""
            return self.call(*args, **kwargs)

        def __repr__(self) -> str:  # pragma: no cover - debugging aid
            return f"FunctionTool(name={self.metadata.name!r}, fallback=True)"

    class _ToolOutput:
        """Minimal stand-in for ``llama_index.core.tools.ToolOutput``."""

        def __init__(
            self,
            content: str,
            tool_name: str,
            raw_input: Dict[str, Any],
            raw_output: Any,
        ) -> None:
            self.content = content
            self.tool_name = tool_name
            self.raw_input = raw_input
            self.raw_output = raw_output
            self.is_error = isinstance(raw_output, dict) and "error" in raw_output

        def __str__(self) -> str:
            return self.content

    class ReActAgent:  # noqa: D401 - placeholder
        """Placeholder for ``llama_index.core.agent.ReActAgent`` (LlamaIndex absent)."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            require_llama_index("llama_index.core.agent.ReActAgent")

        @classmethod
        def from_tools(cls, *args: Any, **kwargs: Any) -> Any:
            require_llama_index("ReActAgent.from_tools")

    class FunctionCallingAgent:  # noqa: D401 - placeholder
        """Placeholder for ``FunctionCallingAgent`` (LlamaIndex absent)."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            require_llama_index("llama_index.core.agent.FunctionCallingAgent")

        @classmethod
        def from_tools(cls, *args: Any, **kwargs: Any) -> Any:
            require_llama_index("FunctionCallingAgent.from_tools")

    return (
        FunctionTool,
        ToolMetadata,
        ReActAgent,
        FunctionCallingAgent,
        require_llama_index,
    )


def _load_real() -> Optional[tuple]:
    """Try to import the real LlamaIndex symbols; return them or ``None``."""
    try:
        from llama_index.core.tools import FunctionTool, ToolMetadata  # type: ignore
    except Exception:
        return None

    # The agent classes moved around across LlamaIndex versions; resolve them
    # defensively so the integration works on a range of releases. Anything we
    # cannot find becomes a placeholder that raises only when actually used.
    react_agent = _resolve_agent_class(
        [
            ("llama_index.core.agent", "ReActAgent"),
            ("llama_index.core.agent.react", "ReActAgent"),
            ("llama_index.core.agent.workflow", "ReActAgent"),
        ],
        "ReActAgent",
    )
    fc_agent = _resolve_agent_class(
        [
            ("llama_index.core.agent", "FunctionCallingAgent"),
            ("llama_index.core.agent.function_calling", "FunctionCallingAgent"),
            ("llama_index.core.agent.workflow", "FunctionAgent"),
        ],
        "FunctionCallingAgent",
    )

    def require_llama_index(feature: str = "this feature") -> None:  # noqa: D401
        """No-op when ``llama-index-core`` is installed."""
        return None

    return FunctionTool, ToolMetadata, react_agent, fc_agent, require_llama_index


def _resolve_agent_class(candidates: List[tuple], label: str):
    """Return the first importable ``(module, attr)`` class, else a placeholder."""
    import importlib

    for module_name, attr in candidates:
        try:
            module = importlib.import_module(module_name)
            cls = getattr(module, attr, None)
            if cls is not None:
                return cls
        except Exception:
            continue

    class _UnavailableAgent:  # pragma: no cover - depends on LlamaIndex version
        """Placeholder when this agent class is missing from the installed LlamaIndex."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError(
                f"{label} is not available in the installed llama-index-core "
                "version. Upgrade llama-index-core, or pass agent_type explicitly "
                "to build_agent()."
            )

        @classmethod
        def from_tools(cls, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError(
                f"{label}.from_tools is not available in the installed "
                "llama-index-core version."
            )

    return _UnavailableAgent


_real = _load_real()
if _real is not None:
    HAS_LLAMA_INDEX = True
    LLAMA_INDEX_IMPORT_ERROR: Optional[BaseException] = None
    (
        FunctionTool,
        ToolMetadata,
        ReActAgent,
        FunctionCallingAgent,
        require_llama_index,
    ) = _real
else:
    HAS_LLAMA_INDEX = False
    try:  # capture a representative import error for diagnostics
        import llama_index.core  # type: ignore  # noqa: F401
    except Exception as _exc:  # pragma: no cover - depends on env
        LLAMA_INDEX_IMPORT_ERROR = _exc
    else:  # pragma: no cover - llama_index.core present but tools import failed
        LLAMA_INDEX_IMPORT_ERROR = None
    (
        FunctionTool,
        ToolMetadata,
        ReActAgent,
        FunctionCallingAgent,
        require_llama_index,
    ) = _make_fallbacks()
