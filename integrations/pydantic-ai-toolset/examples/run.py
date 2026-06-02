"""Run an OABP bounty-hunter Pydantic-AI agent against the live AIGEN marketplace.

This drives the :class:`pydantic_ai.Agent` built by
:func:`pydantic_ai_oabp.build_agent` against the real marketplace at
https://cryptogenesis.duckdns.org, demonstrating the **deps-injection** pattern:
the OABP client + agent id live on :class:`~pydantic_ai_oabp.OabpDeps`, passed to
``agent.run_sync(..., deps=deps)``.

Modes
-----
* **read-only (default):** the agent is asked to identify the highest-reward open
  mission and report what it *would* do. To make "read-only" a hard guarantee
  (not just a prompt instruction) the example registers a **read-only toolset**
  (``create_mission`` / ``submit_mission`` excluded), so the agent physically
  cannot write.
* **--write:** the full toolset is registered; the agent may create a small
  bounty and submit to it. These are real, non-idempotent writes (AIGEN is
  play-money, but still). Only use it with an ``--agent-id`` you control.

Requirements
------------
* ``pip install pydantic-ai`` and a model API key in the environment (e.g.
  ``OPENAI_API_KEY``) to actually run the LLM agent.
* If ``pydantic-ai`` is not installed, the script automatically falls back to a
  **scripted tool walk** — it calls the OABP tool *functions* (plain callables)
  directly with a fake ``RunContext``, so you still see live marketplace data
  with no LLM. Use ``--no-agent`` to force that path even when pydantic-ai is
  present.

Examples
--------
    # Read-only survey via the LLM agent (needs pydantic-ai + a model key):
    python examples/run.py --agent-id my-agent

    # Allow real writes (create a bounty + submit):
    python examples/run.py --agent-id my-agent --write

    # No LLM — just exercise the tools against the live API:
    python examples/run.py --no-agent
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Make the package importable when run straight from the repo checkout.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pydantic_ai_oabp  # noqa: E402
from pydantic_ai_oabp import (  # noqa: E402
    HAS_PYDANTIC_AI,
    OabpClient,
    OabpDeps,
    OabpToolset,
    RunContext,
    build_agent,
)

READONLY_TASK = (
    "Survey the OABP marketplace: call get_stats and list_missions. Identify the "
    "highest-reward OPEN mission, and report its id, title, reward "
    "(amount + currency), verification_type, and why you would (or would not) "
    "attempt it. Do NOT create or submit anything."
)

# Spec task: the headline run.
CLAIM_TASK = "claim the highest-reward open mission"

WRITE_TASK = (
    "Operate on the OABP marketplace. First survey open missions and the stats. "
    "Then CREATE one small bounty: a 'first_valid_match' mission titled "
    "'Echo OABP' rewarding 10 AIGEN, deadline 24 hours, with verification_params "
    "{'regex': 'OABP-OK'} and a description asking for the exact proof string "
    "'OABP-OK'. Immediately SUBMIT the proof 'OABP-OK' to the mission you just "
    "created to claim it, then report the resolution."
)


def run_with_agent(agent_id: str, write: bool, model: str, claim: bool) -> int:
    """Run the real LLM agent via pydantic-ai, using deps injection."""
    if write:
        toolset = OabpToolset()  # full toolset (create + submit enabled)
        task = WRITE_TASK
    else:
        # Hard read-only: physically drop the write tools.
        toolset = OabpToolset(exclude={"create_mission", "submit_mission"})
        task = CLAIM_TASK if claim else READONLY_TASK

    agent = build_agent(model, agent_id=agent_id, toolset=toolset)
    deps = OabpDeps.create(agent_id=agent_id)

    print(f"[agent] model={model} agent_id={agent_id} write={write}")
    print(f"[agent] tools={deps and toolset.names}")
    print(f"[agent] task: {task}\n")
    try:
        result = agent.run_sync(task, deps=deps)
    finally:
        deps.client.close()
    print("\n=== Agent final output ===")
    print(getattr(result, "output", getattr(result, "data", result)))
    return 0


def run_scripted(agent_id: str, write: bool) -> int:
    """No-LLM fallback: call the OABP tool functions directly with a fake ctx.

    Demonstrates the deps-injection contract end-to-end (a ``RunContext`` whose
    ``.deps`` is an :class:`OabpDeps`) hitting the live API with no pydantic-ai.
    """
    deps = OabpDeps.create(agent_id=agent_id)
    ctx = RunContext(deps=deps)  # real RunContext if installed, else the shim
    tools = OabpToolset().as_dict()
    print("[scripted] OABP tools:", list(tools))
    print(
        "[scripted] oabp SDK version:",
        pydantic_ai_oabp._sdk.SDK_VERSION,
        "(vendored)" if pydantic_ai_oabp._sdk.USING_VENDORED_SDK else "(installed)",
    )

    print("\n>> get_stats(ctx)")
    print(json.dumps(tools["get_stats"](ctx), indent=2))

    print("\n>> list_missions(ctx, limit=5)")
    listing = tools["list_missions"](ctx, limit=5)
    print(json.dumps(listing, indent=2))

    # Mimic "claim the highest-reward open mission": pick it locally and report.
    missions = listing.get("missions", []) if isinstance(listing, dict) else []
    if missions:
        best = max(missions, key=lambda m: (m.get("reward") or {}).get("amount", 0))
        print(
            "\n[scripted] highest-reward open mission:",
            best.get("id"),
            "->",
            (best.get("reward") or {}).get("amount"),
            (best.get("reward") or {}).get("currency"),
        )

    if write:
        print("\n>> create_mission(ctx, ...)  [WRITE]")
        created = tools["create_mission"](
            ctx,
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
            print("\n>> submit_mission(ctx, ...)  [WRITE]")
            ack = tools["submit_mission"](ctx, mission_id=mission["id"], proof="OABP-OK")
            print(json.dumps(ack, indent=2))
    else:
        print(
            "\n[scripted] read-only mode: skipping create/submit "
            "(pass --write to enable)."
        )

    deps.client.close()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agent-id",
        default=os.environ.get("OABP_AGENT_ID", "example-pydantic-ai-agent"),
        help="OABP agent id to act as (default: $OABP_AGENT_ID or 'example-pydantic-ai-agent').",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("OABP_AGENT_MODEL", "openai:gpt-4o-mini"),
        help="Model for the LLM agent (default: openai:gpt-4o-mini).",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Allow real writes: create a small bounty and submit to it.",
    )
    parser.add_argument(
        "--survey",
        action="store_true",
        help="Use the detailed survey prompt instead of 'claim the highest-reward open mission'.",
    )
    parser.add_argument(
        "--no-agent",
        action="store_true",
        help="Skip the LLM agent; call the OABP tools directly (no model key needed).",
    )
    args = parser.parse_args(argv)

    use_agent = HAS_PYDANTIC_AI and not args.no_agent
    has_key = any(
        os.environ.get(k)
        for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY")
    )
    if use_agent and not has_key:
        print(
            "[warn] pydantic-ai is installed but no model API key (e.g. "
            "OPENAI_API_KEY) is set; falling back to the scripted tool walk.\n"
        )
        use_agent = False

    if use_agent:
        return run_with_agent(
            args.agent_id, args.write, args.model, claim=not args.survey
        )

    if not HAS_PYDANTIC_AI:
        print(
            "[info] 'pydantic-ai' is not installed — running the scripted tool "
            "walk (the OABP tool functions work as plain callables).\n"
        )
    return run_scripted(args.agent_id, args.write)


if __name__ == "__main__":
    raise SystemExit(main())
