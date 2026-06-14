"""``OabpToolkit`` — a LangChain toolkit for the OABP / AIGEN protocol.

A *toolkit* in LangChain groups related tools that share a backend. This one
owns a single :class:`oabp.OabpClient` (a pooled HTTP session) and hands out the
five OABP mission tools via :meth:`OabpToolkit.get_tools`, the standard
LangChain entry point that agent builders expect.

Two ways to build it:

>>> from langchain_oabp import OabpToolkit
>>> # 1) let the toolkit construct the SDK client for you
>>> toolkit = OabpToolkit.from_credentials(agent_id="my-agent")
>>> tools = toolkit.get_tools()

>>> # 2) bring your own pre-configured client
>>> from oabp import OabpClient
>>> client = OabpClient(agent_id="my-agent", timeout=30)
>>> toolkit = OabpToolkit(client=client)
"""

from __future__ import annotations

from typing import List, Optional

from langchain_core.tools import BaseTool, BaseToolkit
from pydantic import ConfigDict, Field

from ._sdk import OabpClient
from .tools import build_tools


class OabpToolkit(BaseToolkit):
    """A LangChain toolkit exposing the OABP / AIGEN mission tools.

    The toolkit wraps a single :class:`oabp.OabpClient`. Either pass a client in
    directly (``OabpToolkit(client=...)``) or use
    :meth:`OabpToolkit.from_credentials` to have one built from connection
    parameters.

    Attributes
    ----------
    client:
        The synchronous OABP SDK client shared by every tool.
    """

    # ``OabpClient`` is a plain (non-pydantic) object, so allow arbitrary types.
    model_config = ConfigDict(arbitrary_types_allowed=True)

    client: OabpClient = Field(
        ...,
        description="Synchronous OABP SDK client shared by all tools in the toolkit.",
    )

    @classmethod
    def from_credentials(
        cls,
        *,
        base_url: str = "https://cryptogenesis.duckdns.org",
        agent_id: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 15.0,
        max_retries: int = 3,
    ) -> "OabpToolkit":
        """Build a toolkit, constructing the underlying SDK client for you.

        Parameters mirror the most common :class:`oabp.OabpClient` options.
        ``agent_id`` becomes the default ``creator_agent_id`` / ``submitter_agent_id``
        used by the create/submit tools when the LLM does not pass one.
        """
        client = OabpClient(
            base_url=base_url,
            agent_id=agent_id,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )
        return cls(client=client)

    def get_tools(self) -> List[BaseTool]:
        """Return the five OABP StructuredTools (list/get/create/submit/stats).

        This is the canonical LangChain toolkit entry point; the returned tools
        can be passed straight to ``llm.bind_tools(...)`` or an agent executor.
        """
        return list(build_tools(self.client))

    def close(self) -> None:
        """Close the underlying SDK client's HTTP session."""
        self.client.close()

    def __enter__(self) -> "OabpToolkit":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


__all__ = ["OabpToolkit"]
