"""Example: two AutoGen / AG2 agents negotiate over real OABP bounty missions.

A **hunter** agent discovers open missions on the OABP / AIGEN marketplace and
proposes the most promising one; a **verifier** agent evaluates that mission's
verification rules and decides whether the deliverable can be produced and proven
for real (GoPlus token-security / GitHub repo). They talk in a group chat while
calling the live marketplace at https://cryptogenesis.duckdns.org through the
six ``autogen_oabp`` tools.

Two modes
---------
* ``--live`` : real AG2 ``AssistantAgent`` + ``UserProxyAgent`` + ``GroupChat``
  driven by an OpenAI-compatible model (needs ``pyautogen`` installed and
  ``OAI_CONFIG_LIST`` / ``OPENAI_API_KEY`` in the environment). Hits the live
  marketplace.
* default (offline) : a tiny scripted "fake" model + a mocked marketplace, so
  the discover -> evaluate -> submit loop runs with **no AutoGen, no API key and
  no network**. This is what CI / a quick local smoke run uses.

Run::

    python examples/groupchat_quickstart.py            # offline, runs anywhere
    python examples/groupchat_quickstart.py --live     # real AG2 + live API
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List

# Make the package importable when run straight from the repo.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import autogen_oabp  # noqa: E402
from autogen_oabp import OabpClient, get_tools, register_oabp_tools, tool_names  # noqa: E402


HUNTER_SYSTEM = (
    "You are HUNTER, an autonomous agent on the OABP / AIGEN bounty marketplace. "
    "Your job: call list_missions to discover open bounties, then get_mission on "
    "the most promising one, and propose to the VERIFIER which mission to pursue "
    "and what proof would win it. Rewards are paid in AIGEN (uncapped reputation "
    "points) or USDC, minus a 0.5% protocol fee."
)

VERIFIER_SYSTEM = (
    "You are VERIFIER, an autonomous agent on the OABP / AIGEN marketplace. Given "
    "a mission HUNTER proposes, judge whether its deliverable can be produced and "
    "PROVEN for real under its verification_type: 'first_valid_match' needs a "
    "proof matching the regex; 'oracle' is checked for real (GoPlus token-security "
    "for safety reviews, GitHub REST for repo deliverables, no code execution). "
    "If it is winnable, say so and have the deliverable submitted with "
    "submit_mission. Reply TERMINATE when the negotiation is resolved."
)


# --------------------------------------------------------------------------- #
# Live mode: real AG2 agents + GroupChat over the live marketplace
# --------------------------------------------------------------------------- #
def run_live() -> None:
    """Drive a real AG2 GroupChat between hunter and verifier over live missions."""
    from autogen import (
        AssistantAgent,
        GroupChat,
        GroupChatManager,
        UserProxyAgent,
    )

    # OAI_CONFIG_LIST (JSON file path or inline JSON) or OPENAI_API_KEY env var.
    config_list = _load_openai_config()
    llm_config = {"config_list": config_list, "cache_seed": None}

    hunter = AssistantAgent(
        name="hunter", system_message=HUNTER_SYSTEM, llm_config=llm_config
    )
    verifier = AssistantAgent(
        name="verifier", system_message=VERIFIER_SYSTEM, llm_config=llm_config
    )
    # The executor runs whatever tool calls the assistants suggest. It never asks
    # a human and runs no code other than the registered OABP tools.
    executor = UserProxyAgent(
        name="executor",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=10,
        is_termination_msg=lambda m: "TERMINATE" in (m.get("content") or ""),
        code_execution_config=False,
    )

    # One shared, pooled SDK client backs every tool for both agents.
    client = OabpClient(agent_id="hunter")
    # Hunter proposes the discovery/submit calls; verifier proposes evaluation
    # calls; the executor executes them all.
    register_oabp_tools(hunter, executor, client, agent_id="hunter")
    register_oabp_tools(verifier, executor, client, agent_id="verifier")

    groupchat = GroupChat(
        agents=[hunter, verifier, executor],
        messages=[],
        max_round=12,
        speaker_selection_method="round_robin",
    )
    manager = GroupChatManager(groupchat=groupchat, llm_config=llm_config)

    try:
        executor.initiate_chat(
            manager,
            message=(
                "Find an open OABP mission worth pursuing. HUNTER: list and pick "
                "one and propose a proof. VERIFIER: confirm it is winnable under "
                "its verification rules and submit the deliverable."
            ),
        )
    finally:
        client.close()


def _load_openai_config() -> List[Dict[str, Any]]:
    """Load an AG2 config_list from OAI_CONFIG_LIST or OPENAI_API_KEY."""
    raw = os.environ.get("OAI_CONFIG_LIST")
    if raw:
        if os.path.exists(raw):
            with open(raw, "r", encoding="utf-8") as fh:
                return json.load(fh)
        return json.loads(raw)
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        return [{"model": model, "api_key": api_key}]
    raise SystemExit(
        "Live mode needs an OpenAI-compatible config: set OAI_CONFIG_LIST "
        "(path or inline JSON) or OPENAI_API_KEY. Run without --live for the "
        "offline demo."
    )


# --------------------------------------------------------------------------- #
# Offline mode: scripted negotiation over a mocked marketplace (no deps)
# --------------------------------------------------------------------------- #
def _offline_client() -> OabpClient:
    """An OabpClient wired to a fake in-memory marketplace (no network)."""

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
            "id": "m-042",
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
            "id": "m-043",
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
            if method == "GET" and "/api/missions/m-042" in url:
                return _Resp(200, missions[0])
            if method == "POST" and "/missions/m-042/submit" in url:
                return _Resp(
                    200,
                    {
                        "accepted": True,
                        "resolution": {
                            "winner_agent_id": "hunter",
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

    return OabpClient(agent_id="hunter", session=_Session())


def run_offline() -> None:
    """Scripted hunter<->verifier negotiation using the real tool callables."""
    client = _offline_client()
    # These are the exact same callables register_oabp_tools would bind into AG2.
    tools = get_tools(client=client, agent_id="hunter")
    print("OABP tools available:", tool_names())
    print(
        "Backed by oabp SDK version:",
        autogen_oabp._sdk.SDK_VERSION,
        "(vendored)" if autogen_oabp._sdk.USING_VENDORED_SDK else "(installed)",
    )
    print("Marketplace:", autogen_oabp.DEFAULT_BASE_URL, "(mocked offline)\n")

    # 1) HUNTER discovers open missions.
    listing = tools["list_missions"]()
    print(f"[hunter] list_missions -> {listing['count']} open missions")
    for m in listing["missions"]:
        print(
            f"         - {m['id']}: {m['title']} "
            f"({m['reward']['amount']} {m['reward']['currency']}, "
            f"verify={m['verification_type']})"
        )

    # 2) HUNTER picks the oracle-verified safety review and inspects it.
    pick = listing["missions"][0]["id"]
    detail = tools["get_mission"](mission_id=pick)
    print(f"\n[hunter] proposes {pick}: {detail['title']!r}")
    print(
        f"[hunter] -> verifier: this is '{detail['verification_type']}' verified; "
        f"params={detail['verification_params']}"
    )

    # 3) VERIFIER judges winnability under the verification rules.
    vtype = detail["verification_type"]
    print(
        f"[verifier] verification_type={vtype} is permissionless and oracle-backed "
        "(GoPlus). Winnable: submit the token address as proof; the oracle checks "
        "it for real."
    )

    # 4) VERIFIER has the deliverable submitted.
    result = tools["submit_mission"](mission_id=pick, proof="0xC0ffee")
    print(f"\n[verifier] submit_mission -> {json.dumps(result)}")
    res = result.get("response", {}).get("resolution", {})
    if res.get("verified"):
        print(
            f"[verifier] VERIFIED. reward_paid={res.get('reward_paid')} AIGEN "
            "(500 minus the 0.5% protocol fee). TERMINATE."
        )

    client.close()


# --------------------------------------------------------------------------- #
def main(argv: List[str]) -> None:
    if "--live" in argv:
        run_live()
    else:
        run_offline()


if __name__ == "__main__":
    main(sys.argv[1:])
