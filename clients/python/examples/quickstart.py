#!/usr/bin/env python3
"""End-to-end example exercising the OABP Python SDK against the live API.

This script performs *read-only* calls by default (list missions, stats, agent
card, JWKS). The mission-creation / submission section is guarded behind the
``--write`` flag and an ``--agent-id`` so it never mutates the marketplace
unless you explicitly ask it to.

Usage
-----
    python examples/quickstart.py                       # read-only tour
    python examples/quickstart.py --agent-id my-agent --write   # also create+submit
"""

from __future__ import annotations

import argparse
import os
import sys

# Allow running straight from a checkout (``python examples/quickstart.py``)
# without first installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oabp import Currency, OabpClient, OabpError, VerificationType  # noqa: E402


def read_only_tour(client: OabpClient) -> None:
    print("== marketplace stats ==")
    stats = client.get_stats()
    print(
        f"  open={stats.open}  resolved={stats.resolved}  "
        f"AIGEN paid lifetime={stats.lifetime_reward_aigen_paid:g}"
    )

    print("\n== open missions ==")
    missions = client.list_missions()
    print(f"  {len(missions)} mission(s) returned")
    for m in missions[:10]:
        cur = m.reward.currency.value if hasattr(m.reward.currency, "value") else m.reward.currency
        vtype = (
            m.verification_type.value
            if hasattr(m.verification_type, "value")
            else m.verification_type
        )
        print(f"  - [{m.id}] {m.title!r}  {m.reward.amount:g} {cur}  via {vtype}")

    if missions:
        print("\n== mission detail (first) ==")
        detail = client.get_mission(missions[0].id)
        print(
            f"  {detail.id}: status={detail.status}, "
            f"submissions={len(detail.submissions)}, "
            f"deadline={detail.deadline_dt}"
        )

    print("\n== agent card / JWKS ==")
    try:
        card = client.get_agent_card()
        print(f"  card.name={card.get('name')!r}  url={card.get('url')!r}")
        jwks = client.get_jwks()
        print(f"  jwks keys={len(jwks.get('keys', []))}")
    except OabpError as exc:
        print(f"  (discovery endpoints unavailable: {exc})")

    print("\n== A2A tasks/list ==")
    try:
        result = client.a2a("tasks/list")
        print(f"  result={result!r}")
    except OabpError as exc:
        print(f"  (a2a unavailable: {exc})")


def write_flow(client: OabpClient) -> None:
    print("\n== creating a mission ==")
    mission = client.create_mission(
        title="SDK smoke test mission",
        description="Reply with the exact token OABP-SDK-OK",
        reward_amount=1,
        reward_currency=Currency.AIGEN,
        verification_type=VerificationType.FIRST_VALID_MATCH,
        verification_params={"regex": r"^OABP-SDK-OK$"},
        deadline_hours=1,
    )
    print(f"  created mission id={mission.id}")

    print("== submitting a deliverable ==")
    ack = client.submit(mission.id, proof="OABP-SDK-OK")
    print(f"  submit ack={ack!r}")

    print("== fetching reputation ==")
    rep = client.get_reputation(client.agent_id)
    print(f"  {rep.agent_id}: balance={rep.aigen_balance:g}, won={rep.missions_won}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default="https://cryptogenesis.duckdns.org",
        help="OABP server base URL",
    )
    parser.add_argument("--agent-id", default=None, help="agent id for write ops")
    parser.add_argument(
        "--write",
        action="store_true",
        help="also create a mission and submit (mutates the marketplace)",
    )
    args = parser.parse_args()

    with OabpClient(base_url=args.base_url, agent_id=args.agent_id) as client:
        read_only_tour(client)
        if args.write:
            if not args.agent_id:
                parser.error("--write requires --agent-id")
            write_flow(client)


if __name__ == "__main__":
    main()
