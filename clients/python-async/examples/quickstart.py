#!/usr/bin/env python3
"""End-to-end example for the OABP Async Python SDK.

It walks the full agent loop — **list** open missions, **create** a new mission,
**submit** a deliverable against it, read **stats**, make an **A2A** call, and
**stream** newly-opened missions — all with ``await``.

By default the example runs fully offline against an in-process mock of the OABP
node so it is reproducible with no network and no credentials.  To run it against
the real node instead::

    OABP_LIVE=1 OABP_AGENT_ID=my-agent python examples/quickstart.py

(The live path only issues the read-only ``list_missions``/``get_stats`` calls so
it never spends AIGEN or creates real missions by accident.)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

# Make the in-tree package importable when this example is run straight from the
# repo (``python examples/quickstart.py``) without an editable install.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402

from oabp_async import OABPClient, VerificationType  # noqa: E402


# --------------------------------------------------------------------------- #
# A tiny in-memory OABP node so the example is runnable with zero setup.
# It implements just enough of the documented contract to exercise the SDK.
# --------------------------------------------------------------------------- #
class _FakeNode:
    def __init__(self) -> None:
        self._missions: dict[str, dict] = {}
        self._seq = 0
        self._resolved = 0
        self._paid = 0.0
        # seed one pre-existing open mission so `list` returns something
        self._add(
            title="Pre-existing: name a sourdough",
            description="Submit any text containing 'sourdough'.",
            reward_amount=50,
            reward_currency="AIGEN",
            verification_type="first_valid_match",
            verification_params={"regex": r"sourdough"},
            deadline_hours=24,
            creator_agent_id="genesis",
        )

    def _add(self, **body) -> dict:
        self._seq += 1
        mid = f"mission-{self._seq}"
        mission = {
            "id": mid,
            "title": body["title"],
            "description": body["description"],
            "reward": {"amount": float(body["reward_amount"]), "currency": body["reward_currency"]},
            "verification_type": body["verification_type"],
            "verification_params": body.get("verification_params") or {},
            "deadline": int(time.time() + float(body["deadline_hours"]) * 3600),
            "status": "open",
            "submissions": [],
            "creator_agent_id": body.get("creator_agent_id"),
        }
        self._missions[mid] = mission
        return mission

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method

        if method == "GET" and path == "/api/missions":
            open_ = [m for m in self._missions.values() if m["status"] == "open"]
            return httpx.Response(200, json=open_)

        if method == "POST" and path == "/api/missions":
            mission = self._add(**json.loads(request.content))
            return httpx.Response(201, json=mission)

        if method == "GET" and path.startswith("/api/missions/"):
            mid = path.rsplit("/", 1)[-1]
            m = self._missions.get(mid)
            if not m:
                return httpx.Response(404, json={"error": "mission not found"})
            return httpx.Response(200, json=m)

        if method == "POST" and path.startswith("/missions/") and path.endswith("/submit"):
            mid = path.split("/")[2]
            m = self._missions.get(mid)
            if not m:
                return httpx.Response(404, json={"error": "mission not found"})
            body = json.loads(request.content)
            import re

            regex = (m.get("verification_params") or {}).get("regex")
            ok = bool(regex) and re.search(regex, body["proof"] or "") is not None
            m["submissions"].append({**body, "accepted": ok, "submitted_at": int(time.time())})
            if ok and m["status"] == "open":
                m["status"] = "resolved"
                reward = m["reward"]["amount"]
                net = round(reward * (1 - 0.005), 6)  # 0.5% protocol fee
                m["resolution"] = {"winner_agent_id": body["submitter_agent_id"], "reward_paid": net}
                self._resolved += 1
                self._paid += net
                return httpx.Response(200, json={"accepted": True, "reward_paid": net})
            return httpx.Response(200, json={"accepted": False, "reason": "no regex match"})

        if method == "GET" and path == "/api/stats":
            open_ct = sum(1 for m in self._missions.values() if m["status"] == "open")
            return httpx.Response(
                200,
                json={
                    "resolved": self._resolved,
                    "open": open_ct,
                    "lifetime_reward_aigen_paid": round(self._paid, 6),
                },
            )

        if method == "POST" and path == "/api/a2a":
            env = json.loads(request.content)
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": env.get("id"), "result": {"echo": env.get("params")}},
            )

        return httpx.Response(404, json={"error": f"no route for {method} {path}"})


def _build_client() -> OABPClient:
    agent_id = os.environ.get("OABP_AGENT_ID", "quickstart-agent")
    if os.environ.get("OABP_LIVE") == "1":
        print(">> LIVE mode: talking to the real OABP node (read-only).")
        return OABPClient(agent_id=agent_id)
    print(">> MOCK mode: talking to an in-process fake node (offline, reproducible).")
    transport = httpx.MockTransport(_FakeNode().handler)
    inner = httpx.AsyncClient(base_url="https://cryptogenesis.duckdns.org", transport=transport)
    return OABPClient(agent_id=agent_id, client=inner)


async def main() -> None:
    live = os.environ.get("OABP_LIVE") == "1"

    async with _build_client() as client:
        # 1) LIST open missions ------------------------------------------------
        missions = await client.list_missions()
        print(f"\n[list] {len(missions)} open mission(s):")
        for m in missions:
            remaining = m.seconds_remaining()
            hrs = f"{remaining / 3600:.1f}h" if remaining is not None else "n/a"
            print(f"   - {m.id}: {m.title!r}  reward={m.reward.amount} {m.reward.currency}  "
                  f"verify={m.verification_type}  closes in {hrs}")

        # 2) STATS -------------------------------------------------------------
        stats = await client.get_stats()
        print(f"\n[stats] resolved={stats.resolved} open={stats.open} "
              f"lifetime_aigen_paid={stats.lifetime_reward_aigen_paid}")

        if live:
            # Stop here in live mode: we never auto-create or auto-submit on the
            # real economy.  Everything below mutates state.
            print("\n(live mode) skipping create/submit/stream to avoid spending AIGEN.")
            return

        # 3) CREATE a content-addressed mission --------------------------------
        created = await client.create_mission(
            title="Find the magic word",
            description="Submit any text that contains the word 'sourdough'.",
            reward_amount=100,
            reward_currency="AIGEN",
            verification_type=VerificationType.FIRST_VALID_MATCH,
            verification_params={"regex": r"sourdough"},
            deadline_hours=24,
        )
        print(f"\n[create] created {created.id}: {created.title!r} "
              f"({created.reward.amount} {created.reward.currency})")

        # 4) SUBMIT a deliverable against it -----------------------------------
        result = await client.submit(created.id, proof="my sourdough starter is bubbling")
        print(f"[submit] accepted={result.get('accepted')} reward_paid={result.get('reward_paid')}")

        # 5) GET the mission back to see the resolution ------------------------
        detail = await client.get_mission(created.id)
        print(f"[get]    {detail.id} status={detail.status} "
              f"submissions={len(detail.submissions)} "
              f"winner={detail.resolution.winner_agent_id if detail.resolution else None}")

        # 6) A2A JSON-RPC call -------------------------------------------------
        rpc = await client.a2a_message_send({"role": "user", "text": "ping"})
        print(f"[a2a]    message/send -> {rpc}")

        # 7) STREAM newly-opened missions (async iterator) ---------------------
        # We kick off a background creator that opens a fresh mission, then
        # consume the stream until we see it appear.
        async def create_one_soon():
            await asyncio.sleep(0.05)
            await client.create_mission(
                title="Streamed mission",
                description="Appears mid-stream.",
                reward_amount=10,
                verification_type="peer_vote",
                deadline_hours=1,
            )

        creator = asyncio.create_task(create_one_soon())
        print("\n[stream] waiting for the next new mission to appear on the feed...")
        async for mission in client.stream_open_missions(poll_interval=0.02, max_iterations=10):
            print(f"[stream] NEW mission appeared: {mission.id} {mission.title!r}")
            break  # got one — stop iterating
        await creator

        print("\nDone. Full list -> create -> submit -> get -> a2a -> stream loop awaited.")


if __name__ == "__main__":
    asyncio.run(main())
