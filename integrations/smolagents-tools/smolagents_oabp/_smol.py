"""smol-agents compatibility seam for ``smolagents_oabp``.

Hugging Face **smol-agents** turns a plain Python function into a ``Tool`` with
the ``@tool`` decorator. smol-agents builds the tool's machine-facing schema by
parsing the function's **type hints** and its **Google-style ``Args:``
docstring** — so every OABP tool function in :mod:`smolagents_oabp.tools` carries
full type hints and an ``Args:`` block, and that is the single source of truth
for the schema.

This module is the only place that touches smol-agents:

* If **smolagents** is installed, ``tool`` is the real
  :func:`smolagents.tool` decorator, and the OABP tools become genuine
  ``smolagents.Tool`` instances (usable by ``CodeAgent`` / ``ToolCallingAgent``).
* If smolagents is **not** installed, ``tool`` is a *no-op-ish* fallback that
  keeps the decorated function fully **callable** and additionally attaches a
  lightweight, smolagents-shaped descriptor exposing ``.name``, ``.description``,
  ``.inputs`` (a JSON-schema-style mapping parsed from the hints + ``Args:``
  docstring) and ``.output_type``. This means :func:`smolagents_oabp.get_tools`
  returns objects with a real ``name``/``description``/``inputs`` schema whether
  or not smolagents is present, and the underlying function is always callable.

The fallback deliberately mirrors smol-agents' own ``str``→``"string"``,
``int``→``"integer"``, ``float``→``"number"``, ``bool``→``"boolean"``,
``dict``→``"object"`` mapping and its ``Args:``-docstring parsing, so the schema
shape an LLM sees is the same in both modes.
"""

from __future__ import annotations

import functools
import inspect
import re
import typing
from typing import Any, Callable, Dict, Optional, Tuple, get_args, get_origin

try:  # Python 3.9+: Annotated/Union live in typing.
    from typing import Annotated  # noqa: F401
except ImportError:  # pragma: no cover - 3.8 and earlier
    from typing_extensions import Annotated  # type: ignore  # noqa: F401


# --------------------------------------------------------------------------- #
# Detect the real smolagents.tool decorator (optional dependency)
# --------------------------------------------------------------------------- #
def _load_smol_tool() -> Tuple[Optional[Callable[..., Any]], bool]:
    """Return ``(smolagents_tool_decorator_or_None, smolagents_available)``."""
    try:
        from smolagents import tool as _smol_tool  # type: ignore
    except Exception:  # pragma: no cover - exercised only without smolagents
        return None, False
    return _smol_tool, True


_SMOL_TOOL, SMOLAGENTS_AVAILABLE = _load_smol_tool()


# --------------------------------------------------------------------------- #
# Type-hint -> JSON-schema type mapping (matches smol-agents' own mapping)
# --------------------------------------------------------------------------- #
# smol-agents authorizes exactly these JSON-schema type names for tool inputs.
_PY_TO_JSON = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    dict: "object",
    list: "array",
    Any: "any",
    type(None): "null",
}


def _union_origins() -> Tuple[Any, ...]:
    """Origins that mean a Union, covering ``Optional[X]`` and PEP 604 ``X | None``."""
    origins: list = [typing.Union]
    try:  # Python 3.10+: ``X | None`` has origin ``types.UnionType``.
        import types as _types

        if hasattr(_types, "UnionType"):
            origins.append(_types.UnionType)
    except Exception:  # pragma: no cover - defensive
        pass
    return tuple(origins)


_UNION_ORIGINS = _union_origins()


def _is_optional(annotation: Any) -> Tuple[bool, Any]:
    """If ``annotation`` is ``Optional[X]`` / ``X | None`` return ``(True, X)``."""
    origin = get_origin(annotation)
    if origin in _UNION_ORIGINS:
        args = [a for a in get_args(annotation) if a is not type(None)]  # noqa: E721
        if len(args) == 1:
            return True, args[0]
        # Multiple non-None members (rare here) -> treat as the first.
        if args:
            return True, args[0]
    return False, annotation


def _json_type_for(annotation: Any) -> str:
    """Map a (possibly Optional/Annotated/parametrised) hint to a JSON type."""
    if annotation is inspect.Parameter.empty or annotation is None:
        return "any"
    # Unwrap Annotated[...] to its first arg.
    if get_origin(annotation) is not None and hasattr(annotation, "__metadata__"):
        annotation = get_args(annotation)[0]
    _, inner = _is_optional(annotation)
    origin = get_origin(inner)
    if origin in (dict,) or inner is dict:
        return "object"
    if origin in (list, tuple) or inner in (list, tuple):
        return "array"
    return _PY_TO_JSON.get(inner, "string")


# --------------------------------------------------------------------------- #
# Google-style ``Args:`` docstring parsing (matches smol-agents' parser shape)
# --------------------------------------------------------------------------- #
_ARGS_HEADER_RE = re.compile(
    r"\n\s*(Args|Arguments|Parameters)\s*:\s*\n", re.IGNORECASE
)
_SECTION_HEADER_RE = re.compile(
    r"\n\s*(Returns|Raises|Yields|Example|Examples|Note|Notes)\s*:\s*\n",
    re.IGNORECASE,
)
_ARG_LINE_RE = re.compile(
    r"^\s*(?P<name>\*{0,2}[A-Za-z_][A-Za-z0-9_]*)\s*"
    r"(?:\([^)]*\))?\s*:\s*(?P<desc>.*)$"
)


def parse_docstring(doc: Optional[str]) -> Tuple[str, Dict[str, str]]:
    """Split a Google-style docstring into ``(summary, {arg: description})``.

    The summary is everything before the ``Args:`` section; the arg map is the
    per-parameter descriptions inside it. Continuation lines (indented under an
    arg) are folded into that arg's description. This mirrors how smol-agents
    reads a tool function's docstring to populate the input descriptions.
    """
    if not doc:
        return "", {}
    doc = inspect.cleandoc(doc)
    text = "\n" + doc + "\n"
    header = _ARGS_HEADER_RE.search(text)
    summary = doc.split("\n\n", 1)[0].strip() if not header else text[: header.start()].strip()
    if not header:
        return summary, {}

    body = text[header.end():]
    nxt = _SECTION_HEADER_RE.search("\n" + body)
    if nxt:
        body = ("\n" + body)[: nxt.start()]

    args: Dict[str, str] = {}
    current: Optional[str] = None
    for line in body.splitlines():
        if not line.strip():
            continue
        m = _ARG_LINE_RE.match(line)
        if m:
            current = m.group("name").lstrip("*")
            args[current] = m.group("desc").strip()
        elif current is not None:
            args[current] = (args[current] + " " + line.strip()).strip()
    return summary, args


# --------------------------------------------------------------------------- #
# Lightweight Tool descriptor used when smolagents is not installed
# --------------------------------------------------------------------------- #
class _FallbackTool:
    """A smolagents-shaped, **callable** tool wrapper (no smolagents required).

    Exposes the same surface smol-agents' ``Tool`` exposes for our purposes —
    ``name``, ``description``, ``inputs`` (a JSON-schema-style mapping),
    ``output_type`` — and remains directly callable, delegating to the wrapped
    function. It is what ``@tool`` produces when smolagents is absent, so the
    OABP tool functions stay usable (and introspectable) standalone.
    """

    #: marks objects produced by this module's fallback decorator
    is_oabp_fallback_tool = True

    def __init__(self, func: Callable[..., Any]) -> None:
        functools.update_wrapper(self, func)
        self.func = func
        self.name = func.__name__
        summary, arg_docs = parse_docstring(func.__doc__)
        self.description = summary or (func.__doc__ or func.__name__).strip()
        self.inputs = self._build_inputs(func, arg_docs)
        self.output_type = self._infer_output_type(func)

    @staticmethod
    def _build_inputs(
        func: Callable[..., Any], arg_docs: Dict[str, str]
    ) -> Dict[str, Dict[str, Any]]:
        try:
            hints = typing.get_type_hints(func, include_extras=True)
        except Exception:  # pragma: no cover - defensive
            hints = {}
        sig = inspect.signature(func)
        inputs: Dict[str, Dict[str, Any]] = {}
        for pname, param in sig.parameters.items():
            if pname == "self" or param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue
            annotation = hints.get(pname, param.annotation)
            optional, _inner = _is_optional(annotation)
            schema: Dict[str, Any] = {
                "type": _json_type_for(annotation),
                "description": arg_docs.get(pname, ""),
            }
            # smol-agents treats a parameter with a default (or Optional) as
            # not strictly required; it marks those with ``nullable: True``.
            if optional or param.default is not inspect.Parameter.empty:
                schema["nullable"] = True
            inputs[pname] = schema
        return inputs

    @staticmethod
    def _infer_output_type(func: Callable[..., Any]) -> str:
        try:
            hints = typing.get_type_hints(func)
        except Exception:  # pragma: no cover - defensive
            hints = {}
        ret = hints.get("return")
        return _json_type_for(ret) if ret is not None else "object"

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.func(*args, **kwargs)

    # smolagents.Tool exposes a forward()/run-like entry point in some versions;
    # provide a couple of harmless aliases so naive callers keep working.
    def forward(self, *args: Any, **kwargs: Any) -> Any:
        return self.func(*args, **kwargs)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<OABP fallback Tool {self.name!r} inputs={list(self.inputs)}>"


def tool(func: Callable[..., Any]) -> Any:
    """``@tool`` decorator: real smol-agents tool, or a callable fallback.

    * With **smolagents** installed → returns ``smolagents.tool(func)`` (a real
      ``smolagents.Tool``).
    * Without smolagents → returns a :class:`_FallbackTool`: still callable, and
      carrying a parsed ``name`` / ``description`` / ``inputs`` schema, so the
      OABP tools are usable and introspectable standalone.
    """
    if SMOLAGENTS_AVAILABLE and _SMOL_TOOL is not None:
        return _SMOL_TOOL(func)
    return _FallbackTool(func)


def tool_schema(t: Any) -> Dict[str, Any]:
    """Return ``{"name", "description", "inputs", "output_type"}`` for a tool.

    Works for both a real ``smolagents.Tool`` and a :class:`_FallbackTool`,
    reading the attributes smol-agents guarantees on a tool object.
    """
    return {
        "name": getattr(t, "name", None),
        "description": getattr(t, "description", None),
        "inputs": getattr(t, "inputs", {}) or {},
        "output_type": getattr(t, "output_type", None),
    }


def call_tool(t: Any, /, **kwargs: Any) -> Any:
    """Invoke a tool (smolagents or fallback) by keyword arguments.

    smol-agents ``Tool`` objects are callable via ``__call__``; the fallback is
    too. This helper exists so tests / examples can drive a tool uniformly
    without caring which kind it is.
    """
    return t(**kwargs)


__all__ = [
    "tool",
    "tool_schema",
    "call_tool",
    "parse_docstring",
    "SMOLAGENTS_AVAILABLE",
    "_FallbackTool",
]
