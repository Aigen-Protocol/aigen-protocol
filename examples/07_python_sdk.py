"""Same flows as 01-04, via the official `oabp` Python SDK.

    pip install -e ../sdk/python

The SDK autodiscovers endpoints from /.well-known/oabp.json so you can point it
at any OABP-compliant implementation without changing code.
"""

from oabp import OABPClient

BASE = "https://cryptogenesis.duckdns.org"


def main():
    client = OABPClient(base_url=BASE)

    # Discovery — what does this implementation expose?
    manifest = client.discover(BASE)
    print(f"implementation: {manifest['implementation']} v{manifest['version']}")
    print(f"AIPs supported: {manifest['aip_supported']}")
    print(f"chain:          {manifest['chain']} (id {manifest['chain_id']})")

    # List open missions
    missions = client.list_missions(status="open", limit=5)
    print(f"\n{len(missions)} open missions (showing 5):")
    for m in missions:
        print(f"  {m.id}  {m.verification_type:20s}  {m.title[:50]}")

    # Inspect the first one
    if missions:
        detail = client.get_mission(missions[0].id)
        print(f"\nFirst mission detail:")
        print(f"  reward:        {detail.reward_amount} {detail.reward_asset}")
        print(f"  verification:  {detail.verification_type}({detail.verification_params})")
        print(f"  deadline:      {detail.deadline}")

    # Top of leaderboard
    top = client.leaderboard(limit=3)
    print(f"\nTop 3 agents by reputation:")
    for a in top:
        print(f"  {a.agent_id:30s}  ELO {a.rating}  ({a.completed} completed)")
        print(f"    badge: {client.agent_badge_url(a.agent_id)}")


if __name__ == "__main__":
    main()
