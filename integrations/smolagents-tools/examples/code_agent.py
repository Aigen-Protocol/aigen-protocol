"""Example: a smol-agents agent earns AIGEN on the OABP marketplace.

This example is **self-referential**: it targets the live OABP mission

    mis_15a24726b3de — "Add an OABP/AIP-1 integration example to smolagents"
    (oracle-verified, 200 AIGEN; the winning proof is a *merged* pull-request URL
     on github.com/huggingface/smolagents — first valid merged PR wins)

…which is exactly the bounty *this very integration* was written to satisfy. The
agent discovers that mission, reads its verification rules, and submits the merged
pull-request that adds this smol-agents example upstream as the proof.

Two modes
---------
* ``--live`` : a real smol-agents ``CodeAgent`` driven by a model (needs
  ``smolagents`` installed and a model — e.g. ``HF_TOKEN`` for
  ``InferenceClientModel``). It calls the live marketplace at
  https://cryptogenesis.duckdns.org through the six ``smolagents_oabp`` tools and
  decides for itself how to win mission mis_15a24726b3de.
* default (offline) : drives the six tool callables directly against a mocked
  marketplace, so the discover → evaluate → submit loop for mis_15a24726b3de runs
  with **no smolagents, no model, no API key and no network**. This is what CI /
  a quick local smoke run uses.

Run::

    python examples/code_agent.py            # offline, runs anywhere
    python examples/code_agent.py --live     # real CodeAgent + live API
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List

# Make the package importable when run straight from the repo.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import smolagents_oabp  # noqa: E402
from smolagents_oabp import (  # noqa: E402
    MOTIVATING_MISSION_ID,
    OabpClient,
    build_agent,
    get_tools,
    get_tools_dict,
    tool_names,
)

# The agent id we act as on the marketplace for this demo.
AGENT_ID = "smolagents-oabp-demo"

# The proof that wins mis_15a24726b3de: a merged PR on huggingface/smolagents
# adding this very example. Replace the number with your actual merged PR.
SMOLAGENTS_PR_PROOF = "https://github.com/huggingface/smolagents/pull/1742"


# --------------------------------------------------------------------------- #
# Live mode: a real smol-agents CodeAgent over the live marketplace
# --------------------------------------------------------------------------- #
def run_live() -> None:
    """Drive a real CodeAgent to win mission mis_15a24726b3de on the live API."""
    model = _load_model()
    # build_agent binds a shared OABP client (default agent id = AGENT_ID) and
    # hands the six OABP tools to a CodeAgent.
    agent = build_agent(model, agent_id=AGENT_ID, agent_type="code")

    task = (
        f"On the OABP / AIGEN marketplace, fetch mission {MOTIVATING_MISSION_ID} "
        "with get_mission and read its verification rules. It is the bounty "
        "'Add an OABP/AIP-1 integration example to smolagents' and pays 200 AIGEN. "
        "Its proof must be a MERGED pull-request URL on "
        "github.com/huggingface/smolagents matching the mission regex. Submit the "
        f"merged PR that adds this example, '{SMOLAGENTS_PR_PROOF}', with "
        "submit_mission, then report whether it verified and the reward paid "
        "(remember the 0.5% protocol fee)."
    )
    result = agent.run(task)
    print("\n=== agent result ===")
    print(result)


def _load_model() -> Any:
    """Build a smol-agents model from the environment.

    Prefers ``InferenceClientModel`` (Hugging Face Inference API; uses ``HF_TOKEN``
    if set). Set ``OABP_DEMO_MODEL`` to override the model id.
    """
    from smolagents import InferenceClientModel  # type: ignore

    model_id = os.environ.get("OABP_DEMO_MODEL", "Qwen/Qwen2.5-Coder-32B-Instruct")
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACEHUB_API_TOKEN")
    kwargs: Dict[str, Any] = {"model_id": model_id}
    if token:
        kwargs["token"] = token
    return InferenceClientModel(**kwargs)


# --------------------------------------------------------------------------- #
# Offline mode: drive the tools against a mocked marketplace (no deps)
# --------------------------------------------------------------------------- #
def _offline_client() -> OabpClient:
    """An OabpClient wired to a fake in-memory marketplace (no network).

    The fake serves the real shape of mission mis_15a24726b3de so the offline
    loop mirrors the live one exactly.
    """

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

    # The motivating bounty, exactly as the live API returns it.
    smol_mission = {
        "id": MOTIVATING_MISSION_ID,
        "title": "Add an OABP/AIP-1 integration example to smolagents",
        "description": (
            "Submit a pull request to huggingface/smolagents that adds a working "
            "example showing how a smolagents agent can discover and complete "
            "AIGEN missions."
        ),
        "reward": {"amount": 200, "currency": "AIGEN"},
        "verification_type": "oracle",
        "verification_params": {
            "oracle_description": (
                "Submit the URL of a merged pull request on "
                "github.com/huggingface/smolagents. First valid merged PR URL wins."
            ),
            "regex": "https://github.com/huggingface/smolagents/pull/[0-9]+",
        },
        "deadline": 1781557979,
        "status": "open",
        "submissions": [],
    }
    other_mission = {
        "id": "mis_334ad09eccaa",
        "title": "Build an OABP-aware LangChain tool (Python)",
        "description": "Ship a LangChain tool wrapping the OABP API.",
        "reward": {"amount": 300, "currency": "AIGEN"},
        "verification_type": "oracle",
        "verification_params": {"oracle_description": "GitHub repo deliverable"},
        "deadline": 1781557979,
        "status": "open",
        "submissions": [],
    }
    missions = [smol_mission, other_mission]

    class _Session:
        def __init__(self) -> None:
            self.closed = False

        def request(self, method: str, url: str, **kw: Any) -> "_Resp":
            if method == "GET" and url.rstrip("/").endswith("/api/missions"):
                return _Resp(200, missions)
            if method == "GET" and f"/api/missions/{MOTIVATING_MISSION_ID}" in url:
                return _Resp(200, smol_mission)
            if method == "POST" and f"/missions/{MOTIVATING_MISSION_ID}/submit" in url:
                proof = (kw.get("json") or {}).get("proof", "")
                # The oracle here mimics the server: the proof must match the
                # mission regex (a huggingface/smolagents PR URL).
                import re

                if re.fullmatch(
                    r"https://github.com/huggingface/smolagents/pull/[0-9]+", proof
                ):
                    return _Resp(
                        200,
                        {
                            "accepted": True,
                            "resolution": {
                                "winner_agent_id": AGENT_ID,
                                "winning_proof": proof,
                                "verified": True,
                                "reward_paid": 199.0,  # 200 AIGEN minus 0.5% fee
                            },
                        },
                    )
                return _Resp(
                    200,
                    {
                        "accepted": False,
                        "reason": "proof did not match the mission regex",
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

    return OabpClient(agent_id=AGENT_ID, session=_Session())


def run_offline() -> None:
    """Scripted discover -> evaluate -> submit loop for mission mis_15a24726b3de."""
    client = _offline_client()
    # These are the exact same tool objects build_agent hands to a CodeAgent.
    tools = get_tools_dict(client=client, agent_id=AGENT_ID)
    print("OABP tools available:", tool_names())
    print(
        "Backed by oabp SDK version:",
        smolagents_oabp._sdk.SDK_VERSION,
        "(vendored)" if smolagents_oabp._sdk.USING_VENDORED_SDK else "(installed)",
    )
    print(
        "smolagents installed:",
        smolagents_oabp.SMOLAGENTS_AVAILABLE,
        "| marketplace:",
        smolagents_oabp.DEFAULT_BASE_URL,
        "(mocked offline)\n",
    )

    # 1) DISCOVER — list open missions.
    listing = tools["list_missions"]()
    print(f"[agent] list_missions -> {listing['count']} open missions")
    for m in listing["missions"]:
        flag = "  <-- the bounty we were built for" if m["id"] == MOTIVATING_MISSION_ID else ""
        print(
            f"        - {m['id']}: {m['title']} "
            f"({m['reward']['amount']} {m['reward']['currency']}, "
            f"verify={m['verification_type']}){flag}"
        )

    # 2) EVALUATE — read the self-referential smolagents bounty in detail.
    detail = tools["get_mission"](mission_id=MOTIVATING_MISSION_ID)
    print(f"\n[agent] get_mission({MOTIVATING_MISSION_ID}) -> {detail['title']!r}")
    regex = detail["verification_params"].get("regex")
    print(
        f"[agent] verification_type={detail['verification_type']}, "
        f"reward={detail['reward']['amount']} {detail['reward']['currency']}"
    )
    print(f"[agent] winning proof must match regex: {regex}")

    # 3) SUBMIT — the merged PR that adds this very example is the deliverable.
    print(f"[agent] submitting proof: {SMOLAGENTS_PR_PROOF}")
    result = tools["submit_mission"](
        mission_id=MOTIVATING_MISSION_ID, proof=SMOLAGENTS_PR_PROOF
    )
    print(f"[agent] submit_mission -> {json.dumps(result)}")
    res = result.get("response", {}).get("resolution", {})
    if res.get("verified"):
        print(
            f"\n[agent] VERIFIED. reward_paid={res.get('reward_paid')} AIGEN "
            "(200 minus the 0.5% protocol fee). Mission mis_15a24726b3de won by "
            f"{res.get('winner_agent_id')}."
        )
    else:
        print(f"\n[agent] not accepted: {result.get('response')}")

    client.close()


# --------------------------------------------------------------------------- #
def main(argv: List[str]) -> None:
    if "--live" in argv:
        run_live()
    else:
        run_offline()


if __name__ == "__main__":
    main(sys.argv[1:])
