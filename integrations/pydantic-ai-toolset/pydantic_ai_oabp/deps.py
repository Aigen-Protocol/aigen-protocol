"""Dependencies injected into OABP tools via Pydantic-AI's ``RunContext``.

Pydantic-AI's idiom for giving tools access to shared, run-scoped resources is
**dependency injection**: you parametrise an ``Agent[DepsT]`` with a deps type,
pass a concrete ``deps=`` to ``agent.run(...)`` / ``run_sync(...)``, and every
tool receives it as ``ctx.deps`` (where ``ctx: RunContext[DepsT]`` is the tool's
first argument).

:class:`OabpDeps` is that deps object for this integration. It carries:

* an :class:`oabp.OabpClient` (the pooled-HTTP, retrying, typed SDK client), and
* an optional default ``agent_id`` — the OABP identity used as
  ``creator_agent_id`` / ``submitter_agent_id`` / reputation target when the
  model does not pass one.

Because the client lives on the deps (not baked into each tool closure), the same
toolset can be driven as different agents across runs simply by swapping
``deps``::

    agent.run_sync("...", deps=OabpDeps.create(agent_id="agent-a"))
    agent.run_sync("...", deps=OabpDeps.create(agent_id="agent-b"))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ._sdk import OabpClient


@dataclass
class OabpDeps:
    """Run-scoped dependencies for the OABP Pydantic-AI tools.

    Attributes
    ----------
    client:
        The OABP SDK client used to talk to the marketplace. Reused across all
        tool calls in a run (one pooled ``requests.Session``).
    agent_id:
        Default OABP agent id. Used as ``creator_agent_id`` /
        ``submitter_agent_id`` / reputation target when a tool is invoked
        without an explicit one. Falls back to ``client.agent_id`` if left
        ``None`` at construction via :meth:`create`.
    """

    client: OabpClient
    agent_id: Optional[str] = None
    # Free-form bag for application-specific context an integrator may want to
    # thread through (e.g. a budget cap, a logger). Unused by the tools.
    extra: dict = field(default_factory=dict, repr=False)

    @classmethod
    def create(
        cls,
        *,
        agent_id: Optional[str] = None,
        client: Optional[OabpClient] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 15.0,
        max_retries: int = 3,
        **client_kwargs: Any,
    ) -> "OabpDeps":
        """Build :class:`OabpDeps`, constructing an :class:`oabp.OabpClient` if needed.

        Parameters
        ----------
        agent_id:
            Default OABP agent id (see the class docstring). If omitted, it is
            taken from ``client.agent_id``.
        client:
            A pre-configured OABP client to reuse (its pooled session). When
            given, the connection parameters below are ignored.
        base_url, api_key, timeout, max_retries, **client_kwargs:
            Forwarded to a freshly-built :class:`oabp.OabpClient` when ``client``
            is not supplied. ``base_url`` defaults to the SDK default
            (``https://cryptogenesis.duckdns.org``).
        """
        if client is None:
            kwargs: dict = {
                "agent_id": agent_id,
                "api_key": api_key,
                "timeout": timeout,
                "max_retries": max_retries,
                **client_kwargs,
            }
            if base_url:
                kwargs["base_url"] = base_url
            client = OabpClient(**kwargs)
            effective_agent = agent_id
        else:
            effective_agent = (
                agent_id if agent_id is not None else getattr(client, "agent_id", None)
            )
        return cls(client=client, agent_id=effective_agent)

    # Convenience: resolve "the agent id to act as" for a given call.
    def resolve_agent_id(self, override: Optional[str] = None) -> Optional[str]:
        """Return ``override`` if set, else the deps' default ``agent_id``."""
        return override if override else self.agent_id


__all__ = ["OabpDeps"]
