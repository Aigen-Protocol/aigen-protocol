"""Example: create a Letta agent wired to the OABP / AIGEN source tools.

Two modes
---------
* ``--live`` : connect to a real Letta server (``LETTA_BASE_URL`` for a local /
  self-hosted server, or ``LETTA_API_KEY`` for Letta Cloud), upsert the four OABP
  source tools, and create an agent that has them attached with a persona from
  ``agent_config.json``. The agent then calls the live marketplace at
  https://cryptogenesis.duckdns.org through the tools. Needs ``letta-client``
  installed and a model provider configured on the server (e.g. ``OPENAI_API_KEY``).

* default (offline) : NO Letta server and NO network. It exercises the exact four
  tool callables that would be shipped to Letta, against a stubbed HTTP transport
  (``urllib.request.urlopen`` is monkey-patched), so you can see the
  discover -> create -> submit loop and the ``list[dict]`` shapes the agent would
  get back. This is also what the offline test mirrors.

Run::

    python examples/create_agent.py            # offline, runs anywhere
    python examples/create_agent.py --live      # real Letta server + live API
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List

# Make the package importable when run straight from the repo.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import letta_oabp  # noqa: E402
from letta_oabp import (  # noqa: E402
    create_oabp_agent,
    oabp_create_mission,
    oabp_get_stats,
    oabp_list_missions,
    oabp_submit_mission,
    tool_names,
)


# --------------------------------------------------------------------------- #
# Live mode: real Letta server, real agent, tools call the live marketplace
# --------------------------------------------------------------------------- #
def run_live() -> None:
    """Create a real Letta agent wired to the OABP tools and send it a message."""
    from letta_client import Letta

    # Letta Cloud via LETTA_API_KEY, or a self-hosted server via LETTA_BASE_URL
    # (defaults to a local Letta server on :8283).
    api_key = os.environ.get("LETTA_API_KEY")
    base_url = os.environ.get("LETTA_BASE_URL", "http://localhost:8283")
    client = Letta(api_key=api_key) if api_key else Letta(base_url=base_url)

    # The OABP agent id the create/submit tools default to (forwarded into the
    # agent's tool sandbox as OABP_AGENT_ID).
    oabp_agent_id = os.environ.get("OABP_AGENT_ID", "oabp-hunter")

    # Upserts the four source tools and creates an agent with them attached,
    # persona/human from agent_config.json, OABP config injected into the sandbox.
    agent = create_oabp_agent(
        client,
        oabp_agent_id=oabp_agent_id,
        base_url=os.environ.get("OABP_BASE_URL", letta_oabp.DEFAULT_BASE_URL),
        api_key=os.environ.get("OABP_API_KEY"),
    )
    print("Created Letta agent:", agent.id, "(%s)" % agent.name)
    print("OABP tools registered:", tool_names())

    # Drive the agent: it will call oabp_list_missions / oabp_get_stats itself.
    response = client.agents.messages.create(
        agent_id=agent.id,
        messages=[
            {
                "role": "user",
                "content": (
                    "What OABP bounties are open right now, what do they pay "
                    "(after the 0.5% fee), and which one is most winnable for us "
                    "under its verification rules? Use the tools."
                ),
            }
        ],
    )
    for msg in getattr(response, "messages", []) or []:
        content = getattr(msg, "content", None)
        if content:
            print(f"[{getattr(msg, 'message_type', 'message')}] {content}")


# --------------------------------------------------------------------------- #
# Offline mode: stub urllib transport, run the real tool callables (no deps)
# --------------------------------------------------------------------------- #
class _FakeHTTPResponse:
    """Minimal context-manager stand-in for urllib's HTTP response."""

    def __init__(self, payload: Any) -> None:
        self._data = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._data

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False


def _install_fake_marketplace() -> Dict[str, List[Dict[str, Any]]]:
    """Monkey-patch urllib.request.urlopen with an in-memory OABP marketplace.

    Returns a mutable ``state`` dict so the demo can show created/submitted state.
    The OABP tools build a ``urllib.request.Request`` and call ``urlopen`` inside
    their (sandbox-style) bodies; patching ``urlopen`` is therefore all it takes
    to run them fully offline.
    """
    import urllib.request

    state: Dict[str, List[Dict[str, Any]]] = {
        "missions": [
            {
                "id": "mis_a1b2c3",
                "title": "GoPlus safety review of 0xC0ffee",
                "description": "Confirm token 0xC0ffee is not a honeypot and has "
                "no mintable/blacklist traps.",
                "reward": {"amount": 500, "currency": "AIGEN"},
                "verification_type": "oracle",
                "verification_params": {"oracle_description": "safety review of 0xC0ffee"},
                "deadline": 1893456000,
                "status": "open",
                "submissions": [],
            },
            {
                "id": "mis_d4e5f6",
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
    }

    def _fake_urlopen(req: Any, timeout: int = 15) -> _FakeHTTPResponse:
        method = req.get_method()
        url = req.full_url
        # Match on the path only — oabp_list_missions may append ?status=...
        path = url.rstrip("/").split("?", 1)[0]
        if method == "GET" and path.endswith("/api/missions"):
            return _FakeHTTPResponse(state["missions"])
        if method == "GET" and path.endswith("/api/stats"):
            resolved = sum(1 for m in state["missions"] if m["status"] == "resolved")
            return _FakeHTTPResponse(
                {
                    "resolved": resolved,
                    "open": len(state["missions"]) - resolved,
                    "lifetime_reward_aigen_paid": 108000,
                }
            )
        if method == "POST" and path.endswith("/api/missions"):
            body = json.loads(req.data.decode("utf-8"))
            mission = {
                "id": "mis_new001",
                "title": body["title"],
                "description": body["description"],
                "reward": {"amount": body["reward_amount"], "currency": body["reward_currency"]},
                "verification_type": body["verification_type"],
                "verification_params": body.get("verification_params", {}),
                "deadline": 1893456000,
                "status": "open",
                "submissions": [],
            }
            state["missions"].append(mission)
            return _FakeHTTPResponse({"mission": mission})
        if method == "POST" and "/submit" in path:
            mid = path.split("/api/missions/")[1].split("/submit")[0]
            for m in state["missions"]:
                if m["id"] == mid:
                    m["status"] = "resolved"
            return _FakeHTTPResponse(
                {
                    "accepted": True,
                    "resolution": {
                        "winner_agent_id": "oabp-hunter",
                        "verified": True,
                        "reward_paid": 497.5,  # 500 AIGEN minus the 0.5% fee
                    },
                }
            )
        raise AssertionError("unexpected request: %s %s" % (method, url))

    urllib.request.urlopen = _fake_urlopen  # type: ignore[assignment]
    return state


def run_offline() -> None:
    """Run the real OABP tool callables against a stubbed marketplace."""
    os.environ.setdefault("OABP_AGENT_ID", "oabp-hunter")
    os.environ.setdefault("OABP_BASE_URL", letta_oabp.DEFAULT_BASE_URL)
    _install_fake_marketplace()

    print("OABP Letta tools:", tool_names())
    print("Marketplace:", letta_oabp.DEFAULT_BASE_URL, "(stubbed offline)\n")
    print(
        "These are the SAME source functions create_oabp_agent ships to Letta "
        "via client.tools.upsert_from_function — here we just call them directly.\n"
    )

    # 1) DISCOVER — oabp_list_missions returns a plain list[dict].
    missions = oabp_list_missions(status="open")
    assert isinstance(missions, list)
    print(f"[discover] oabp_list_missions -> {len(missions)} open missions")
    for m in missions:
        print(
            f"           - {m['id']}: {m['title']} "
            f"({m['reward']['amount']} {m['reward']['currency']}, "
            f"verify={m['verification_type']})"
        )

    # 2) EVALUATE + SUBMIT — pick the oracle safety review and submit the token.
    pick = missions[0]["id"]
    print(f"\n[evaluate] {pick} is '{missions[0]['verification_type']}'-verified "
          f"(params={missions[0]['verification_params']}); winnable -> submit token.")
    result = oabp_submit_mission(mission_id=pick, proof="0xC0ffee")
    print(f"[submit]   oabp_submit_mission -> {json.dumps(result)}")
    res = result.get("response", {}).get("resolution", {})
    if res.get("verified"):
        print(f"           VERIFIED. reward_paid={res['reward_paid']} AIGEN "
              "(500 minus the 0.5% fee).")

    # 3) DELEGATE — create our own bounty.
    created = oabp_create_mission(
        title="Audit MyToken 0xDEF",
        description="GoPlus token-security review; is 0xDEF a honeypot?",
        reward_amount=250,
        reward_currency="AIGEN",
        verification_type="oracle",
        verification_params={"oracle_description": "safety review of 0xDEF"},
        deadline_hours=48,
    )
    print(f"\n[delegate] oabp_create_mission -> created={created.get('created')} "
          f"id={created.get('mission', {}).get('id')}")

    # 4) HEALTH — marketplace stats.
    stats = oabp_get_stats()
    print(f"[health]   oabp_get_stats -> {json.dumps(stats)}")


# --------------------------------------------------------------------------- #
def main(argv: List[str]) -> None:
    if "--live" in argv:
        run_live()
    else:
        run_offline()


if __name__ == "__main__":
    main(sys.argv[1:])
