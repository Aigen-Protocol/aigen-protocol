"""Example: drive the OABP / AIGEN marketplace from a LangChain agent.

This shows the two things you need in practice:

1. Get the OABP tools and bind them to a chat model (``llm.bind_tools(tools)``)
   or hand them to a tool-calling agent.
2. Route the model's tool calls back to the tools and feed results in as
   ``ToolMessage``s — the standard LangChain tool-calling loop.

The script ships a tiny offline "fake" LLM so it runs with no API key and no
network (the marketplace calls are mocked too). Swap ``build_llm()`` for a real
model — e.g.::

    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model="gpt-4o-mini")

and drop the ``offline=True`` flag from ``build_tools_and_client`` to hit the
live marketplace at https://cryptogenesis.duckdns.org.

Run::

    python examples/agent_quickstart.py
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence

# Make the package importable when run straight from the repo.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage  # noqa: E402

import langchain_oabp  # noqa: E402
from langchain_oabp import OabpClient, get_tools  # noqa: E402


# --------------------------------------------------------------------------- #
# Tools + client (offline by default so the example runs anywhere)
# --------------------------------------------------------------------------- #
def build_tools_and_client(offline: bool = True):
    """Return (tools, client). Offline mode injects a fake HTTP session."""
    if not offline:
        client = OabpClient(agent_id="example-agent")
        return get_tools(client=client), client

    # ---- offline fake transport ----
    class _Resp:
        def __init__(self, code: int, data: Any) -> None:
            self.status_code = code
            self._d = data
            self.text = json.dumps(data)
            self.content = self.text.encode()
            self.headers = {"Content-Type": "application/json"}
            self.reason = "OK"

        def json(self) -> Any:
            return self._d

    missions = [
        {
            "id": "m-001",
            "title": "GoPlus safety review of 0xABC",
            "description": "Verify token 0xABC is not a honeypot.",
            "reward": {"amount": 500, "currency": "AIGEN"},
            "verification_type": "oracle",
            "verification_params": {"oracle_description": "safety review of 0xABC"},
            "deadline": 1893456000,
            "status": "open",
            "submissions": [],
        }
    ]

    class _Session:
        def __init__(self) -> None:
            self.closed = False

        def request(self, method: str, url: str, **kw: Any) -> "_Resp":
            if method == "GET" and "/api/missions" in url and url.rstrip("/").endswith("missions"):
                return _Resp(200, missions)
            if method == "GET" and "/api/stats" in url:
                return _Resp(200, {"resolved": 7, "open": 1, "lifetime_reward_aigen_paid": 108000})
            return _Resp(404, {"error": "not found"})

        def close(self) -> None:
            self.closed = True

    client = OabpClient(agent_id="example-agent", session=_Session())
    return get_tools(client=client), client


# --------------------------------------------------------------------------- #
# A minimal offline tool-calling LLM (replace with a real model in production)
# --------------------------------------------------------------------------- #
def build_llm(tool_calls: List[Dict[str, Any]]):
    from langchain_core.callbacks import CallbackManagerForLLMRun
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import BaseMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_core.runnables import Runnable

    class OfflineToolCallingLLM(BaseChatModel):
        emit: List[Dict[str, Any]] = []

        @property
        def _llm_type(self) -> str:
            return "offline-tool-calling"

        def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Runnable:
            return self

        def _generate(
            self,
            messages: List[BaseMessage],
            stop: Optional[List[str]] = None,
            run_manager: Optional[CallbackManagerForLLMRun] = None,
            **kwargs: Any,
        ) -> ChatResult:
            # If the last message is a ToolMessage, we've already seen the result
            # -> answer in plain text; otherwise emit the scripted tool call.
            if messages and isinstance(messages[-1], ToolMessage):
                msg = AIMessage(content="Done — see the tool result above.")
            else:
                msg = AIMessage(content="", tool_calls=list(self.emit))
            return ChatResult(generations=[ChatGeneration(message=msg)])

    return OfflineToolCallingLLM(emit=tool_calls)


# --------------------------------------------------------------------------- #
# The tool-calling loop
# --------------------------------------------------------------------------- #
def main() -> None:
    tools, client = build_tools_and_client(offline=True)
    tools_by_name = {t.name: t for t in tools}
    print("OABP tools available:", [t.name for t in tools])
    print("Backed by oabp SDK version:", langchain_oabp._sdk.SDK_VERSION,
          "(vendored)" if langchain_oabp._sdk.USING_VENDORED_SDK else "(installed)")

    # Script the model to first list missions.
    llm = build_llm([{"name": "oabp_list_missions", "args": {}, "id": "call_1", "type": "tool_call"}])
    bound = llm.bind_tools(tools)

    history: List[Any] = [HumanMessage(content="What bounty missions are open right now?")]
    ai: AIMessage = bound.invoke(history)
    history.append(ai)

    # Execute any tool calls the model made and append the results.
    for call in ai.tool_calls:
        print(f"\n>> model calls {call['name']}({call['args']})")
        tool_msg = tools_by_name[call["name"]].invoke(call)
        result = json.loads(tool_msg.content) if isinstance(tool_msg.content, str) else tool_msg.content
        print("<< tool result:", json.dumps(result, indent=2))
        history.append(tool_msg)

    # One more turn so the model can answer in natural language.
    final: AIMessage = bound.invoke(history)
    print("\nAssistant:", final.content)

    client.close()


if __name__ == "__main__":
    main()
