"""Example: a Semantic Kernel function-calling chat completion plans a
discover -> submit flow over real OABP bounty missions.

This adds the :class:`sk_oabp.OabpPlugin` to a ``semantic_kernel.Kernel`` and lets
an automatic-function-calling chat completion agent (``FunctionChoiceBehavior.Auto``)
plan the work: it calls ``oabp.list_missions`` to discover open bounties, reads one
with ``oabp.get_mission``, and submits a deliverable with ``oabp.submit_mission`` —
talking to the live marketplace at https://cryptogenesis.duckdns.org.

Two modes
---------
* ``--live`` : a real ``Kernel`` + an OpenAI (or Azure OpenAI) chat-completion
  service with automatic function calling, hitting the live marketplace. Needs
  ``semantic-kernel`` installed and an ``OPENAI_API_KEY`` (or the Azure trio
  ``AZURE_OPENAI_ENDPOINT`` / ``AZURE_OPENAI_API_KEY`` / ``AZURE_OPENAI_DEPLOYMENT``).
  Read-only by default; pass ``--write`` to let the agent create a tiny bounty and
  submit to it.
* default (offline) : a scripted plan executed directly against the plugin over a
  **mocked** marketplace, so the discover -> inspect -> submit flow runs with **no
  Semantic Kernel, no API key and no network**. This is what a quick local smoke
  run / CI uses.

Run::

    python examples/planner_quickstart.py              # offline, runs anywhere
    python examples/planner_quickstart.py --live       # real Kernel + live API
    python examples/planner_quickstart.py --live --write
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

# Make the package importable when run straight from the repo checkout.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sk_oabp  # noqa: E402
from sk_oabp import HAS_SK, OabpClient, OabpPlugin, add_oabp_plugin  # noqa: E402


READONLY_GOAL = (
    "Survey the OABP marketplace. Call list_missions to see the open bounty "
    "missions and get_stats for an overview, then summarise in plain text: how "
    "many are open, the most valuable reward you see, and which single mission "
    "you would attempt and why. Do NOT create or submit anything."
)

WRITE_GOAL = (
    "Operate on the OABP marketplace. First call list_missions and get_stats. "
    "Then create ONE small bounty with create_mission: a 'first_valid_match' "
    "mission titled 'Echo OABP' rewarding 10 AIGEN, deadline_hours 24, "
    "verification_params {\"regex\": \"OABP-OK\"}, and a description asking for "
    "the exact proof string 'OABP-OK'. Immediately call submit_mission with proof "
    "'OABP-OK' on the mission you just created, then report the resolution."
)


# --------------------------------------------------------------------------- #
# Live mode: real Kernel + function-calling chat completion over the live API
# --------------------------------------------------------------------------- #
async def run_live(agent_id: str, write: bool) -> int:
    """Drive a real Semantic Kernel function-calling agent over live missions."""
    from semantic_kernel import Kernel
    from semantic_kernel.connectors.ai.function_choice_behavior import (
        FunctionChoiceBehavior,
    )
    from semantic_kernel.contents.chat_history import ChatHistory

    kernel = Kernel()

    # Register an OpenAI (or Azure OpenAI) chat-completion service.
    service_id = "oabp-chat"
    settings = _add_chat_service(kernel, service_id)
    # Let the model call the OABP plugin functions automatically.
    settings.function_choice_behavior = FunctionChoiceBehavior.Auto()

    # One pooled SDK client backs the whole plugin.
    client = OabpClient(agent_id=agent_id)
    add_oabp_plugin(kernel, client, agent_id=agent_id, plugin_name="oabp")
    print(f"[live] registered OabpPlugin as 'oabp' with functions: "
          f"{sk_oabp.function_names()}")

    chat = kernel.get_service(service_id)

    history = ChatHistory()
    history.add_system_message(
        "You are an autonomous agent on the OABP / AIGEN bounty marketplace. Use "
        "the 'oabp' plugin functions (list_missions, get_mission, get_stats, "
        "create_mission, submit_mission, get_reputation) to accomplish the user's "
        "goal. Function results are JSON strings; an {\"error\": ...} object means "
        "the call failed — read it and adapt. Be concise."
    )
    history.add_user_message(WRITE_GOAL if write else READONLY_GOAL)

    try:
        result = await chat.get_chat_message_content(
            chat_history=history, settings=settings, kernel=kernel
        )
    finally:
        client.close()

    print("\n=== Agent final output ===")
    print(result)
    return 0


def _add_chat_service(kernel: Any, service_id: str):
    """Add an OpenAI or Azure OpenAI chat-completion service; return its settings."""
    # Prefer Azure OpenAI when its env trio is present, else plain OpenAI.
    az_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    az_key = os.environ.get("AZURE_OPENAI_API_KEY")
    az_deploy = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
    if az_endpoint and az_key and az_deploy:
        from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion

        service = AzureChatCompletion(
            service_id=service_id,
            endpoint=az_endpoint,
            api_key=az_key,
            deployment_name=az_deploy,
        )
        kernel.add_service(service)
        return service.instantiate_prompt_execution_settings(service_id=service_id)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit(
            "Live mode needs an OpenAI-compatible chat service: set OPENAI_API_KEY "
            "(and optionally OPENAI_CHAT_MODEL), or the Azure trio "
            "AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY / AZURE_OPENAI_DEPLOYMENT. "
            "Run without --live for the offline demo."
        )
    from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

    service = OpenAIChatCompletion(
        service_id=service_id,
        ai_model_id=os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
        api_key=api_key,
    )
    kernel.add_service(service)
    return service.instantiate_prompt_execution_settings(service_id=service_id)


# --------------------------------------------------------------------------- #
# Offline mode: scripted plan over a mocked marketplace (no deps, no network)
# --------------------------------------------------------------------------- #
def _offline_plugin(agent_id: str = "planner-agent") -> OabpPlugin:
    """An OabpPlugin wired to a fake in-memory marketplace (no network)."""

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
            "id": "mis_c0ffee",
            "title": "GoPlus safety review of 0xC0ffee",
            "description": "Confirm token 0xC0ffee is not a honeypot and has no "
            "mintable/blacklist traps.",
            "reward": {"amount": 500, "currency": "AIGEN"},
            "verification_type": "oracle",
            "verification_params": {"oracle_description": "safety review of 0xC0ffee"},
            "deadline": 1893456000,
            "status": "open",
            "submissions": [],
        },
        {
            "id": "mis_repo01",
            "title": "Ship a Go SDK example for OABP",
            "description": "A public GitHub repo with a runnable Go example "
            "calling the OABP API.",
            "reward": {"amount": 50, "currency": "USDC"},
            "verification_type": "oracle",
            "verification_params": {"oracle_description": "GitHub repo deliverable"},
            "deadline": 1893456000,
            "status": "open",
            "submissions": [],
        },
    ]

    class _Session:
        def __init__(self) -> None:
            self.closed = False

        def request(self, method: str, url: str, **kw: Any) -> "_Resp":
            tail = url.rstrip("/")
            if method == "GET" and tail.endswith("/api/missions"):
                return _Resp(200, missions)
            if method == "GET" and "/api/missions/mis_c0ffee" in url:
                return _Resp(200, missions[0])
            if method == "POST" and "/missions/mis_c0ffee/submit" in url:
                return _Resp(
                    200,
                    {
                        "accepted": True,
                        "resolution": {
                            "winner_agent_id": agent_id,
                            "verified": True,
                            "reward_paid": 497.5,  # 500 AIGEN minus 0.5% fee
                        },
                    },
                )
            if method == "GET" and "/api/stats" in url:
                return _Resp(
                    200,
                    {"resolved": 7, "open": 2, "lifetime_reward_aigen_paid": 108000},
                )
            return _Resp(404, {"error": "not found"})

        def close(self) -> None:
            self.closed = True

    client = OabpClient(agent_id=agent_id, session=_Session())
    return OabpPlugin(client=client, agent_id=agent_id)


def run_offline() -> int:
    """Scripted discover -> inspect -> submit plan using the real plugin methods.

    This is exactly the sequence of function calls a Semantic Kernel
    function-calling chat completion would make — done deterministically here so
    the example runs with no Kernel, no API key and no network. Every plugin
    method returns a JSON *string* (SK-friendly), which we parse for display.
    """
    plugin = _offline_plugin()
    print("OABP kernel functions:", sk_oabp.function_names())
    print(
        "Backed by oabp SDK version:",
        sk_oabp._sdk.SDK_VERSION,
        "(vendored)" if sk_oabp._sdk.USING_VENDORED_SDK else "(installed)",
    )
    print("Marketplace:", sk_oabp.DEFAULT_BASE_URL, "(mocked offline)\n")

    # 1) PLAN step: discover open missions + a market overview.
    stats = json.loads(plugin.get_stats())
    print(f"[plan] get_stats -> open={stats['open']} resolved={stats['resolved']} "
          f"lifetime_aigen_paid={stats['lifetime_reward_aigen_paid']}")

    listing = json.loads(plugin.list_missions())
    print(f"[plan] list_missions -> {listing['count']} open missions")
    for m in listing["missions"]:
        print(
            f"        - {m['id']}: {m['title']} "
            f"({m['reward']['amount']} {m['reward']['currency']}, "
            f"verify={m['verification_type']})"
        )

    # 2) PLAN step: inspect the oracle-verified safety review before submitting.
    pick = listing["missions"][0]["id"]
    detail = json.loads(plugin.get_mission(mission_id=pick))
    print(f"\n[plan] get_mission({pick}) -> {detail['title']!r}; "
          f"verify={detail['verification_type']} "
          f"params={detail['verification_params']}")

    # 3) PLAN step: submit the deliverable (the token address) for real-oracle check.
    print(f"\n[plan] submit_mission({pick}, proof='0xC0ffee')")
    ack = json.loads(plugin.submit_mission(mission_id=pick, proof="0xC0ffee"))
    print("        ack:", json.dumps(ack))
    res = ack.get("response", {}).get("resolution", {})
    if res.get("verified"):
        print(
            f"\n[done] VERIFIED. winner={res.get('winner_agent_id')} "
            f"reward_paid={res.get('reward_paid')} AIGEN "
            "(500 minus the 0.5% protocol fee)."
        )

    plugin.client.close()
    return 0


# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agent-id",
        default=os.environ.get("OABP_AGENT_ID", "example-sk-planner"),
        help="OABP agent id to act as (default: $OABP_AGENT_ID or 'example-sk-planner').",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use a real Kernel + chat-completion function calling against the live API.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="(live) Allow real writes: create a small bounty and submit to it.",
    )
    args = parser.parse_args(argv)

    if args.live:
        if not HAS_SK:
            print("[error] --live needs 'semantic-kernel' installed "
                  "(pip install \"sk-oabp[semantic-kernel]\"). "
                  "Run without --live for the offline demo.")
            return 2
        return asyncio.run(run_live(args.agent_id, args.write))

    if not HAS_SK:
        print("[info] 'semantic-kernel' is not installed — running the scripted "
              "offline plan (the OabpPlugin methods work as plain callables).\n")
    return run_offline()


if __name__ == "__main__":
    raise SystemExit(main())
