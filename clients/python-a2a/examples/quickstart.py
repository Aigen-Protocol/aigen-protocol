#!/usr/bin/env python3
"""Quickstart for the OABP A2A Python client.

Read-only by default: it fetches + verifies the agent card, lists open missions,
shows protocol stats, and lists this agent's A2A tasks. Pass ``--send "text"`` to
send an A2A message, or ``--create``/``--submit`` to exercise the write paths.

    python examples/quickstart.py                      # read-only tour
    python examples/quickstart.py --send "hello there"
    python examples/quickstart.py --create             # create a demo mission
    python examples/quickstart.py --submit MISSION_ID --proof "alpha-1"

Set OABP_BASE_URL / OABP_AGENT_ID / OABP_API_KEY to override defaults.
"""

from __future__ import annotations

import argparse
import os
import sys

# Allow running straight from a checkout (without `pip install -e .`): make the
# repo root importable so `oabp_a2a` resolves.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oabp_a2a import A2AClient, OABPError, SignatureError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="OABP A2A client quickstart")
    parser.add_argument("--base-url", default=os.environ.get("OABP_BASE_URL"))
    parser.add_argument(
        "--agent-id", default=os.environ.get("OABP_AGENT_ID", "oabp-py-quickstart")
    )
    parser.add_argument("--api-key", default=os.environ.get("OABP_API_KEY"))
    parser.add_argument("--send", metavar="TEXT", help="send an A2A message")
    parser.add_argument("--create", action="store_true", help="create a demo mission")
    parser.add_argument("--submit", metavar="MISSION_ID", help="submit to a mission")
    parser.add_argument("--proof", default="https://example.com/proof")
    args = parser.parse_args()

    kwargs = {"agent_id": args.agent_id, "api_key": args.api_key}
    if args.base_url:
        kwargs["base_url"] = args.base_url

    with A2AClient(**kwargs) as client:
        print(f"# OABP @ {client.base_url} as {client.agent_id}\n")

        # 1. Agent card + signature verification.
        try:
            card = client.fetch_and_verify_agent_card()
            print("[card] signature VERIFIED")
            print(f"       name={card.payload.get('name')!r} kid={card.kid!r}")
        except SignatureError as exc:
            print(f"[card] SIGNATURE INVALID: {exc}")
        except OABPError as exc:
            print(f"[card] could not fetch/verify: {exc}")

        # 2. Protocol stats.
        try:
            stats = client.stats()
            print(
                f"\n[stats] resolved={stats.resolved} open={stats.open} "
                f"lifetime_AIGEN_paid={stats.lifetime_reward_aigen_paid}"
            )
        except OABPError as exc:
            print(f"[stats] error: {exc}")

        # 3. Open missions.
        try:
            missions = client.list_missions()
            print(f"\n[missions] {len(missions)} open")
            for m in missions[:10]:
                print(
                    f"  - {m.id}: {m.title!r} reward={m.reward.amount} "
                    f"{m.reward.currency} via {m.verification_type}"
                )
        except OABPError as exc:
            print(f"[missions] error: {exc}")

        # 4. This agent's tasks.
        try:
            tasks = client.list_tasks(length=5)
            print(f"\n[tasks] {len(tasks)} task(s)")
            for t in tasks:
                print(f"  - {t.id} state={t.status_state}")
        except OABPError as exc:
            print(f"[tasks] error: {exc}")

        # 5. Optional write paths.
        if args.send:
            task = client.send_message(args.send)
            print(f"\n[send] task={task.id} state={task.status_state}")
            if task.history:
                print(f"       reply: {task.history[-1].text!r}")

        if args.create:
            mission = client.create_mission(
                title="Demo: find the magic word",
                description="Submit a string matching ^alpha-[0-9]+$.",
                reward_amount=1,
                verification_type="first_valid_match",
                verification_params={"regex": r"^alpha-[0-9]+$"},
                deadline_hours=24,
            )
            print(f"\n[create] mission={mission.id} status={mission.status}")

        if args.submit:
            res = client.submit(args.submit, args.proof)
            print(f"\n[submit] -> {res}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
