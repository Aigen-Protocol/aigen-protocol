"""Optional-dependency shim for Haystack 2.x (``haystack-ai``).

The point of this integration is to expose OABP marketplace operations as native
Haystack 2.x components — classes decorated with :func:`haystack.component` whose
``run`` method is annotated with :func:`haystack.component.output_types` — and to
bind them to a Haystack :class:`~haystack.tools.Tool`/``ToolInvoker`` via
:class:`~haystack.tools.ComponentTool`. But the spec also requires the package to
remain **importable when ``haystack-ai`` is not installed**, with:

* the :func:`component` class decorator degrading to a **no-op** so the decorated
  classes are still ordinary classes whose ``run(...)`` stays directly callable;
* :func:`component.output_types` degrading to a **no-op** method decorator so
  ``run`` keeps its plain Python signature;
* :func:`ComponentTool` / :func:`Pipeline` becoming lightweight stand-ins that
  either work (a minimal Pipeline that wires ``run`` outputs to inputs) or raise a
  clear, actionable error only *when actually used*.

This module is the single seam that makes all of that true. Every other module
imports these names from here, never from ``haystack`` directly, so the
presence/absence decision lives in exactly one place. :data:`HAS_HAYSTACK`
reflects reality.

The fallbacks mirror just enough of the real Haystack 2.x API for the OABP
components to be defined, introspected, executed, and chained offline:

* ``component`` — class decorator that records the declared ``output_types`` on
  the class (``__haystack_output__``) and marks it (``__haystack_component__``),
  exactly like the markers real Haystack sets, so downstream code can introspect
  a component's outputs without Haystack installed.
* ``component.output_types(**types)`` — method decorator that stashes
  ``_output_types`` on the wrapped ``run`` and returns it unchanged (run stays
  callable).
* ``Pipeline`` — a minimal sequential runner supporting ``add_component`` /
  ``connect`` / ``run`` so ``examples/pipeline.py`` executes end-to-end even
  without ``haystack-ai``.
* ``ComponentTool`` — wraps a component and exposes ``name`` / ``description`` /
  ``parameters`` (a JSON schema derived from ``run``'s signature) and an
  ``invoke(**kwargs)`` that calls the component's ``run``, so the OABP components
  can be surfaced as ``Tool``-like objects for a ``ToolInvoker``/Agent.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, get_type_hints

__all__ = [
    "HAS_HAYSTACK",
    "HAYSTACK_IMPORT_ERROR",
    "component",
    "Pipeline",
    "Tool",
    "ComponentTool",
    "default_to_dict",
    "default_from_dict",
    "require_haystack",
    "component_output_types",
    "component_run_parameters",
]


# --------------------------------------------------------------------------- #
# Introspection helpers (work identically in both modes)
# --------------------------------------------------------------------------- #
def component_output_types(component_obj: Any) -> Dict[str, Any]:
    """Return a component's declared ``run`` output types as ``{name: type}``.

    Reads the markers Haystack (and our fallback) set: the class-level
    ``__haystack_output__`` (the real Haystack stores a ``Sockets`` object there;
    we normalise it) or the ``_output_types`` stashed on ``run`` by
    :func:`component.output_types`.
    """
    # Real Haystack: instances carry __haystack_output__ describing the sockets.
    sockets = getattr(component_obj, "__haystack_output__", None)
    if sockets is not None:
        # Real Haystack Sockets expose a mapping of name -> OutputSocket(.type).
        raw = getattr(sockets, "_sockets_dict", None)
        if isinstance(raw, dict):
            return {name: getattr(sock, "type", Any) for name, sock in raw.items()}
        if isinstance(sockets, dict):
            return dict(sockets)
    run = getattr(component_obj, "run", None)
    declared = getattr(run, "_output_types", None)
    if isinstance(declared, dict):
        return dict(declared)
    return {}


_EMPTY = inspect.Parameter.empty


def _py_type_to_json(annotation: Any) -> Dict[str, Any]:
    """Best-effort JSON-schema fragment for a Python annotation (tool params)."""
    mapping = {
        str: {"type": "string"},
        bool: {"type": "boolean"},
        int: {"type": "integer"},
        float: {"type": "number"},
        dict: {"type": "object"},
        Dict: {"type": "object"},
        list: {"type": "array"},
        List: {"type": "array"},
    }
    if annotation in mapping:
        return dict(mapping[annotation])
    origin = getattr(annotation, "__origin__", None)
    if origin in (dict,):
        return {"type": "object"}
    if origin in (list,):
        return {"type": "array"}
    # Optional[...] / Union[...] -> fall through to permissive.
    return {}


def component_run_parameters(component_obj: Any) -> Dict[str, Any]:
    """Derive an OpenAI-style JSON-schema ``parameters`` block from ``run``.

    Mirrors what Haystack's :class:`ComponentTool` produces from a component's
    ``run`` signature: each non-``self`` parameter becomes a property; those
    without a default become ``required``.
    """
    run = getattr(component_obj, "run", None)
    if run is None:
        return {"type": "object", "properties": {}, "required": []}
    try:
        sig = inspect.signature(run)
    except (TypeError, ValueError):
        return {"type": "object", "properties": {}, "required": []}
    try:
        hints = get_type_hints(run)
    except Exception:
        hints = {}

    properties: Dict[str, Any] = {}
    required: List[str] = []
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        annotation = hints.get(name, param.annotation)
        schema = _py_type_to_json(annotation) if annotation is not _EMPTY else {}
        properties[name] = schema or {}
        if param.default is _EMPTY:
            required.append(name)
    return {"type": "object", "properties": properties, "required": required}


def _required_satisfied(component_obj: Any, supplied: Dict[str, Any]) -> bool:
    """True if every required ``run`` parameter is present in ``supplied``.

    Used by the fallback :class:`Pipeline` to decide whether a component is ready
    to execute (matching real Haystack, which only runs a component once all its
    mandatory inputs are available).
    """
    params = component_run_parameters(component_obj)
    required = params.get("required", [])
    return all(key in supplied for key in required)


# --------------------------------------------------------------------------- #
# Fallback implementations (used when haystack-ai is NOT installed)
# --------------------------------------------------------------------------- #
def _make_fallbacks():
    """Build the no-``haystack`` fallbacks. Returns the public symbols."""

    class _MissingHaystackDependency(RuntimeError):
        """Raised when a Haystack feature is used without ``haystack-ai``."""

    def require_haystack(feature: str = "this feature") -> None:
        raise _MissingHaystackDependency(
            f"{feature} requires the 'haystack-ai' package, which is not "
            "installed. Install it with `pip install haystack-ai` (or "
            '`pip install "haystack-oabp[haystack]"`). The OABP components '
            "themselves still import and their run() methods still work as "
            "plain callables without it."
        )

    class _ComponentDecorator:
        """No-op stand-in for the real ``haystack.component`` decorator object.

        Real Haystack's ``component`` is a callable singleton that is *also* a
        namespace carrying ``output_types`` / ``_component`` helpers. Our
        fallback keeps the decorated class a perfectly ordinary class (so
        ``run`` stays callable) while still stamping the same introspection
        markers Haystack would, and recording the declared output types from
        ``run._output_types`` onto the class as ``__haystack_output__``.
        """

        def __call__(self, cls: Type) -> Type:
            # Mark the class the way Haystack does, for downstream introspection.
            cls.__haystack_component__ = True  # type: ignore[attr-defined]
            run = getattr(cls, "run", None)
            declared = getattr(run, "_output_types", None)
            if isinstance(declared, dict):
                # Store a plain mapping; component_output_types() reads it back.
                cls.__haystack_output__ = dict(declared)  # type: ignore[attr-defined]
            # Provide a default to_dict/from_dict if the class didn't define one,
            # matching the @component contract (serialisable components).
            if not hasattr(cls, "to_dict"):
                def _to_dict(self) -> Dict[str, Any]:
                    return default_to_dict(self, **getattr(self, "_init_params", {}))

                cls.to_dict = _to_dict  # type: ignore[attr-defined]
            if not hasattr(cls, "from_dict"):
                @classmethod
                def _from_dict(klass, data: Dict[str, Any]):
                    return default_from_dict(klass, data)

                cls.from_dict = _from_dict  # type: ignore[attr-defined]
            return cls

        @staticmethod
        def output_types(**types: Any) -> Callable[[Callable], Callable]:
            """No-op method decorator: stash declared output types on ``run``.

            Returns the wrapped function unchanged so ``run(...)`` stays directly
            callable when ``haystack-ai`` is absent.
            """

            def decorator(func: Callable) -> Callable:
                func._output_types = dict(types)  # type: ignore[attr-defined]
                return func

            return decorator

        def _component(self, cls: Type, **_kwargs: Any) -> Type:
            return self.__call__(cls)

    component = _ComponentDecorator()

    def default_to_dict(obj: Any, **init_params: Any) -> Dict[str, Any]:
        """Mirror ``haystack.core.serialization.default_to_dict``."""
        return {
            "type": f"{type(obj).__module__}.{type(obj).__qualname__}",
            "init_parameters": dict(init_params),
        }

    def default_from_dict(cls: Type, data: Dict[str, Any]) -> Any:
        """Mirror ``haystack.core.serialization.default_from_dict``."""
        init_params = (data or {}).get("init_parameters", {}) or {}
        return cls(**init_params)

    class Tool:
        """Lightweight stand-in for ``haystack.tools.Tool``.

        Carries the four things an LLM/``ToolInvoker`` needs — ``name``,
        ``description``, a JSON-schema ``parameters`` block, and an ``invoke``
        callable — and is itself invokable via :meth:`invoke`.
        """

        is_haystack_oabp_fallback = True

        def __init__(
            self,
            name: str,
            description: str,
            parameters: Dict[str, Any],
            function: Callable[..., Any],
            *,
            outputs_to_string: Optional[Dict[str, Any]] = None,
            inputs_from_state: Optional[Dict[str, Any]] = None,
            outputs_to_state: Optional[Dict[str, Any]] = None,
        ) -> None:
            self.name = name
            self.description = description
            self.parameters = parameters
            self.function = function
            self.outputs_to_string = outputs_to_string
            self.inputs_from_state = inputs_from_state
            self.outputs_to_state = outputs_to_state

        def invoke(self, **kwargs: Any) -> Any:
            return self.function(**kwargs)

        def __call__(self, **kwargs: Any) -> Any:
            return self.invoke(**kwargs)

        def tool_spec(self) -> Dict[str, Any]:
            """OpenAI function-calling spec for this tool."""
            return {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }

        def __repr__(self) -> str:  # pragma: no cover - debugging aid
            return f"Tool(name={self.name!r}, fallback=True)"

    class ComponentTool(Tool):
        """Stand-in for ``haystack.tools.ComponentTool``.

        Wraps a Haystack-style component so it can be used as a ``Tool``: derives
        ``parameters`` from the component's ``run`` signature and routes
        :meth:`invoke` to ``component.run(**kwargs)`` (returning the dict of
        outputs, exactly like a real Haystack component run).
        """

        def __init__(
            self,
            component: Any,
            *,
            name: Optional[str] = None,
            description: Optional[str] = None,
            parameters: Optional[Dict[str, Any]] = None,
            outputs_to_string: Optional[Dict[str, Any]] = None,
            inputs_from_state: Optional[Dict[str, Any]] = None,
            outputs_to_state: Optional[Dict[str, Any]] = None,
        ) -> None:
            self._component = component
            resolved_name = name or _snake(type(component).__name__)
            resolved_desc = description or (type(component).__doc__ or "").strip().split("\n")[0]
            resolved_params = parameters or component_run_parameters(component)
            super().__init__(
                name=resolved_name,
                description=resolved_desc or resolved_name,
                parameters=resolved_params,
                function=component.run,
                outputs_to_string=outputs_to_string,
                inputs_from_state=inputs_from_state,
                outputs_to_state=outputs_to_state,
            )

        @property
        def component(self) -> Any:
            return self._component

        def __repr__(self) -> str:  # pragma: no cover - debugging aid
            return f"ComponentTool(name={self.name!r}, fallback=True)"

    class Pipeline:
        """Minimal sequential stand-in for ``haystack.Pipeline``.

        Implements just enough of the real API — ``add_component(name, comp)``,
        ``connect("a.out", "b.in")`` and ``run(data)`` — to execute a *linear*
        pipeline of OABP components (plus any plain-callable filter component)
        offline. Components run in the order they connect; each connection maps a
        named output of the upstream component to a named input of the
        downstream one. ``run`` returns ``{component_name: outputs}`` for the
        leaf (terminal) components, mirroring Haystack's return shape.

        This is intentionally simple (no branching/looping); the real
        ``haystack.Pipeline`` handles arbitrary DAGs. When ``haystack-ai`` is
        installed the real class is used instead.
        """

        is_haystack_oabp_fallback = True

        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            self._components: Dict[str, Any] = {}
            # edges: (from_comp, from_socket, to_comp, to_socket)
            self._edges: List[Tuple[str, str, str, str]] = []

        def add_component(self, name: str, instance: Any) -> None:
            if name in self._components:
                raise ValueError(f"component named {name!r} already added")
            self._components[name] = instance

        def connect(self, sender: str, receiver: str) -> "Pipeline":
            from_comp, _, from_sock = sender.partition(".")
            to_comp, _, to_sock = receiver.partition(".")
            if from_comp not in self._components:
                raise ValueError(f"unknown sender component {from_comp!r}")
            if to_comp not in self._components:
                raise ValueError(f"unknown receiver component {to_comp!r}")
            # Default sockets: single declared output / first run param.
            if not from_sock:
                outs = list(component_output_types(self._components[from_comp]))
                from_sock = outs[0] if outs else "output"
            if not to_sock:
                params = component_run_parameters(self._components[to_comp])
                props = list(params.get("properties", {}))
                to_sock = props[0] if props else "input"
            self._edges.append((from_comp, from_sock, to_comp, to_sock))
            return self

        def _execution_order(self) -> List[str]:
            """Topological-ish order for a linear pipeline (Kahn's algorithm)."""
            indeg = {name: 0 for name in self._components}
            adj: Dict[str, List[str]] = {name: [] for name in self._components}
            for frm, _fs, to, _ts in self._edges:
                indeg[to] += 1
                adj[frm].append(to)
            order: List[str] = []
            queue = [n for n, d in indeg.items() if d == 0]
            while queue:
                node = queue.pop(0)
                order.append(node)
                for nxt in adj[node]:
                    indeg[nxt] -= 1
                    if indeg[nxt] == 0:
                        queue.append(nxt)
            # Any leftover (shouldn't happen for a DAG) appended for safety.
            for name in self._components:
                if name not in order:
                    order.append(name)
            return order

        def run(self, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            data = dict(data or {})
            order = self._execution_order()
            # Per-component accumulated inputs (start from user-provided data).
            pending: Dict[str, Dict[str, Any]] = {
                name: dict(data.get(name, {})) for name in self._components
            }
            outputs: Dict[str, Dict[str, Any]] = {}
            has_outgoing = {frm for frm, _fs, _to, _ts in self._edges}
            ran: set = set()

            for name in order:
                comp = self._components[name]
                kwargs = pending.get(name, {})
                # Mirror real Haystack: only run a component once all its
                # *mandatory* run() inputs are satisfied (by user data or an
                # upstream output). A component whose required inputs are unmet —
                # e.g. a submitter with no connection feeding it in read-only
                # mode — is simply skipped, not executed with missing args.
                if not _required_satisfied(comp, kwargs):
                    continue
                result = comp.run(**kwargs)
                result = result if isinstance(result, dict) else {"output": result}
                outputs[name] = result
                ran.add(name)
                # Feed declared connections downstream.
                for frm, fs, to, ts in self._edges:
                    if frm == name and fs in result:
                        pending[to][ts] = result[fs]
            # Return only terminal components (no outgoing edge) that actually
            # ran, like Haystack returns the outputs of leaf components.
            return {
                name: outs
                for name, outs in outputs.items()
                if name not in has_outgoing
            }

        def to_dict(self) -> Dict[str, Any]:
            return {
                "components": {
                    name: (comp.to_dict() if hasattr(comp, "to_dict") else {})
                    for name, comp in self._components.items()
                },
                "connections": [
                    {"sender": f"{frm}.{fs}", "receiver": f"{to}.{ts}"}
                    for frm, fs, to, ts in self._edges
                ],
            }

    return (
        component,
        Pipeline,
        Tool,
        ComponentTool,
        default_to_dict,
        default_from_dict,
        require_haystack,
    )


def _snake(name: str) -> str:
    """Convert a ClassName to snake_case (matches Haystack's default tool name)."""
    out: List[str] = []
    for i, ch in enumerate(name):
        if ch.isupper() and i and (not name[i - 1].isupper()):
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


# --------------------------------------------------------------------------- #
# Try the real Haystack first; fall back to the shim otherwise.
# --------------------------------------------------------------------------- #
def _load_real() -> Optional[tuple]:
    """Try to import the real Haystack 2.x symbols; return them or ``None``."""
    try:
        from haystack import Pipeline, component  # type: ignore
        from haystack.core.serialization import (  # type: ignore
            default_from_dict,
            default_to_dict,
        )
        from haystack.tools import ComponentTool, Tool  # type: ignore
    except Exception:
        return None

    def require_haystack(feature: str = "this feature") -> None:  # noqa: D401
        """No-op when ``haystack-ai`` is installed."""
        return None

    return (
        component,
        Pipeline,
        Tool,
        ComponentTool,
        default_to_dict,
        default_from_dict,
        require_haystack,
    )


_real = _load_real()
if _real is not None:
    HAS_HAYSTACK = True
    HAYSTACK_IMPORT_ERROR: Optional[BaseException] = None
    (
        component,
        Pipeline,
        Tool,
        ComponentTool,
        default_to_dict,
        default_from_dict,
        require_haystack,
    ) = _real
else:
    HAS_HAYSTACK = False
    try:  # capture a representative import error for diagnostics
        import haystack  # type: ignore  # noqa: F401
    except Exception as _exc:  # pragma: no cover - depends on env
        HAYSTACK_IMPORT_ERROR = _exc
    else:  # pragma: no cover - haystack present but a submodule import failed
        HAYSTACK_IMPORT_ERROR = None
    (
        component,
        Pipeline,
        Tool,
        ComponentTool,
        default_to_dict,
        default_from_dict,
        require_haystack,
    ) = _make_fallbacks()
