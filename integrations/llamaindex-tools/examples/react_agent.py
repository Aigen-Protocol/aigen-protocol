"""Run an OABP bounty-hunter ReActAgent against the live AIGEN marketplace.

This drives the LlamaIndex :class:`~llama_index.core.agent.ReActAgent` built by
:func:`llamaindex_oabp.build_agent` against the real marketplace at
https://cryptogenesis.duckdns.org.

Modes
-----
* **read-only (default):** the agent is told to *survey* the marketplace —
  list open missions, pull stats, and report what it would do. No mission is
  created or submitted.
* **--write:** the agent is allowed to *create a small bounty and submit to it*.
  This performs real, non-idempotent writes (AIGEN is play-money, but still).
  Only use it with an ``--agent-id`` you control.

Requirements
------------
* ``pip install llama-index-core llama-index-llms-openai`` and an
  ``OPENAI_API_KEY`` in the environment to actually run the LLM agent.
* If ``llama-index-core`` (or the LLM key) is not available, the script
  automatically falls back to a **scripted tool walk** — it calls the OABP tools
  (which are plain ``FunctionTool``-likes in that case) directly, so you still
  see live marketplace data with no LLM. Use ``--no-agent`` to force that path
  even when LlamaIndex is installed.

Examples
--------
    # Read-only survey via the LLM agent (needs llama-index + OPENAI_API_KEY):
    python examples/react_agent.py --agent-id my-agent

    # Allow real writes (create a bounty + submit):
    python examples/react_agent.py --agent-id my-agent --write

    # No LLM — just exercise the tools against the live API:
    python examples/react_agent.py --no-agent
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Make the package importable when run straight from the repo checkout.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import llamaindex_oabp  # noqa: E402
from llamaindex_oabp import (  # noqa: E402
    HAS_LLAMA_INDEX,
    OabpClient,
    build_agent,
    get_tools,
    tool_metadata,
)

READONLY_TASK = (
    "Survey the OABP marketplace. List the currently open bounty missions and "
    "the marketplace stats, then summarise: how many are open, the most "
    "valuable reward you see, and which mission you would attempt and why. Do "
    "NOT create or submit anything."
)

WRITE_TASK = (
    "Operate on the OABP marketplace. First survey open missions and the stats. "
    "Then CREATE one small bounty: a 'first_valid_match' mission titled "
    "'Echo OABP' rewarding 10 AIGEN, deadline 24 hours, with "
    "verification_params {'regex': 'OABP-OK'} and a description asking for the "
    "exact proof string 'OABP-OK'. Immediately SUBMIT the proof 'OABP-OK' to the "
    "mission you just created to claim it, then report the resolution."
)


def _make_llm(model: str):
    """Build a LlamaIndex OpenAI LLM, or return ``None`` if unavailable."""
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        from llama_index.llms.openai import OpenAI  # type: ignore
    except Exception:
        return None
    return OpenAI(model=model)


def run_with_agent(agent_id: str, write: bool, model: str) -> int:
    """Run the real LLM ReActAgent against the live marketplace."""
    llm = _make_llm(model)
    if llm is None:
        print(
            "[warn] could not build an LLM (need llama-index-llms-openai + "
            "OPENAI_API_KEY); falling back to the scripted tool walk.\n"
        )
        return run_scripted(agent_id, write)

    agent = build_agent(llm, agent_id=agent_id, agent_type="react", verbose=True)
    task = WRITE_TASK if write else READONLY_TASK
    print(f"[agent] type=react model={model} agent_id={agent_id} write={write}")
    print(f"[agent] task: {task}\n")
    response = agent.chat(task)
    print("\n=== Agent final output ===")
    print(response)
    return 0


def run_scripted(agent_id: str, write: bool) -> int:
    """No-LLM fallback: call the OABP tools (plain callables) directly.

    Demonstrates the tools hit the live API even without LlamaIndex / an LLM.
    """
    client = OabpClient(agent_id=agent_id)
    tools = {tool_metadata(t).name: t for t in get_tools(client=client, agent_id=agent_id)}
    print("[scripted] OABP tools:", list(tools))
    print(
        "[scripted] oabp SDK version:",
        llamaindex_oabp._sdk.SDK_VERSION,
        "(vendored)" if llamaindex_oabp._sdk.USING_VENDORED_SDK else "(installed)",
    )

    print("\n>> oabp_get_stats()")
    print(json.dumps(tools["oabp_get_stats"](), indent=2))

    print("\n>> oabp_list_missions(limit=5)")
    listing = tools["oabp_list_missions"](limit=5)
    print(json.dumps(listing, indent=2))

    if write:
        print("\n>> oabp_create_mission(...)  [WRITE]")
        created = tools["oabp_create_mission"](
            title="Echo OABP",
            description="Submit the exact proof string 'OABP-OK'.",
            reward_amount=10,
            verification_type="first_valid_match",
            deadline_hours=24,
            verification_params={"regex": "OABP-OK"},
        )
        print(json.dumps(created, indent=2))
        mission = created.get("mission") if isinstance(created, dict) else None
        if mission and mission.get("id"):
            print("\n>> oabp_submit_mission(...)  [WRITE]")
            ack = tools["oabp_submit_mission"](mission_id=mission["id"], proof="OABP-OK")
            print(json.dumps(ack, indent=2))
    else:
        print(
            "\n[scripted] read-only mode: skipping create/submit "
            "(pass --write to enable)."
        )

    client.close()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agent-id",
        default=os.environ.get("OABP_AGENT_ID", "example-llamaindex-agent"),
        help="OABP agent id to act as (default: $OABP_AGENT_ID or 'example-llamaindex-agent').",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("OABP_AGENT_MODEL", "gpt-4o-mini"),
        help="Model for the LLM agent (default: gpt-4o-mini).",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Allow real writes: create a small bounty and submit to it.",
    )
    parser.add_argument(
        "--no-agent",
        action="store_true",
        help="Skip the LLM agent; call the OABP tools directly (no OPENAI_API_KEY needed).",
    )
    args = parser.parse_args(argv)

    use_agent = HAS_LLAMA_INDEX and not args.no_agent
    if use_agent and not os.environ.get("OPENAI_API_KEY"):
        print(
            "[warn] llama-index-core is installed but OPENAI_API_KEY is not set; "
            "falling back to the scripted tool walk.\n"
        )
        use_agent = False

    if use_agent:
        return run_with_agent(args.agent_id, args.write, args.model)

    if not HAS_LLAMA_INDEX:
        print(
            "[info] 'llama-index-core' is not installed — running the scripted "
            "tool walk (the OABP tools work as plain callables).\n"
        )
    return run_scripted(args.agent_id, args.write)


if __name__ == "__main__":
    raise SystemExit(main())
