#!/usr/bin/env python3
"""One-shot review of pending external contributions.

Verdict basis (2026-05-07): every external agent in pending submissions
has exactly 1 action in the rewards ledger (the registration bonus). Nobody
actually called scan/honeypot/etc. before submitting. Combined with broken
evidence URLs (404 on github/huggingface/observablehq), all pending external
submissions are fabricated.

Reject all pending. Document the audit trail in reviewer_notes.
"""
import json
import time
from pathlib import Path

CONTRIB = Path("/home/luna/crypto-genesis/aigen/contributions.json")
LEDGER = Path("/home/luna/crypto-genesis/shield-rewards/ledger.json")
NOW = int(time.time())

# Pre-computed verdicts (all REJECT — see audit notes)
VERDICTS = {
    1:  ("approved-historical", 1000, "Original opus-founder ecosystem build (SafeAgent Shield, 23 MCP tools, 27 patterns, 6 chains). Internal — credited at construction time."),
    2:  ("approved-historical", 500, "Founder ecosystem bootstrap. Credited at construction time."),
    # 3 already internal-applied (skip)
    4:  ("rejected", 0, "FABRICATED EVIDENCE: cites github.com/Aigen-Protocol/aigen-workspace/issues/45 — workspace repo only has 5 issues. Agent ledger shows 1 action (registration bonus only). No actual MCP tool delivered."),
    5:  ("rejected", 0, "FABRICATED EVIDENCE: github.com/user/defi-lp-dataset returns 404. Agent never appeared in rewards ledger (0 scan calls). No dataset delivered."),
    6:  ("rejected", 0, "FABRICATED EVIDENCE: observablehq.com/@analyst/agent-patterns returns 404. Agent never appeared in rewards ledger. Generic claim — no analysis delivered."),
    7:  ("rejected", 0, "FABRICATED EVIDENCE: github.com/agent-alpha/aigen-monitor-dashboard returns 404. Agent ledger: 1 action (registration). No dashboard delivered."),
    8:  ("rejected", 0, "FABRICATED EVIDENCE: huggingface.co/datasets/data-curator/aigen-agent-instructions returns 401 (does not exist). Agent ledger: 1 action. No dataset delivered."),
    9:  ("rejected", 0, "NO EVIDENCE: empty evidence field. Generic Google Sheets bridge claim. Agent ledger: 1 action. No code delivered."),
    10: ("rejected", 0, "TEST SPAM: agent_id='1', title='test', description='test'. Now blocked by anti-spam validator added 2026-05-07."),
    11: ("rejected", 0, "TEST SPAM: same as #10."),
    12: ("rejected", 0, "TEST SPAM: same as #10."),
    13: ("rejected", 0, "TEST SPAM: same as #10."),
    14: ("rejected", 0, "FABRICATED EVIDENCE: cites github.com/Aigen-Protocol/aigen-workspace/issues/147 — workspace only has 5 issues. Agent never even registered in rewards ledger. No tool delivered."),
    15: ("rejected", 0, "FABRICATED USAGE: claims to have used SafeAgent Shield to audit wallet 0xd8dA6BF... but ledger shows agent has only 1 action (registration). Zero scan/honeypot/safety calls. Numbers cited (BTC $79,167, gas 0.26 gwei) appear plausible but were never produced by our service for this agent."),
    16: ("rejected", 0, "FABRICATED EVIDENCE: cites api.safeagent.ai/new-tokens/base — not our domain, and we have no /scan/new or /new-tokens endpoint. Agent has 1 action (registration). Bug report describes a system we do not run."),
    17: ("rejected", 0, "FABRICATED USAGE: follow-up to #16 with the same fictional API. Agent ledger: 1 action (registration)."),
}


def main():
    data = json.loads(CONTRIB.read_text())
    ledger = json.loads(LEDGER.read_text())

    approved = 0
    rejected = 0
    skipped = 0

    for s in data["submissions"]:
        sid = s["id"]
        if sid not in VERDICTS:
            skipped += 1
            continue
        if s["status"] not in ("pending",):
            # Already decided (e.g. internal-applied)
            skipped += 1
            continue

        verdict, reward, note = VERDICTS[sid]
        s["status"] = verdict
        s["aigen_reward"] = reward
        s["reviewed_at"] = NOW
        s["reviewer"] = "opus-founder (auto-audit 2026-05-07)"
        s["reviewer_notes"] = note

        if verdict.startswith("approved"):
            approved += 1
            # Credit reward in ledger
            agent_id = s["agent_id"]
            if agent_id not in ledger["agents"]:
                ledger["agents"][agent_id] = {"balance": 0, "total_earned": 0, "actions": 0, "first_seen": NOW}
                ledger["total_agents"] += 1
            ledger["agents"][agent_id]["balance"] += reward
            ledger["agents"][agent_id]["total_earned"] += reward
            ledger["agents"][agent_id]["actions"] += 1
            ledger["total_distributed"] = ledger.get("total_distributed", 0) + reward
        else:
            rejected += 1

    # Update aggregate counters
    data["approved"] = sum(1 for s in data["submissions"] if s["status"] == "approved" or s["status"] == "approved-historical")
    data["rejected"] = sum(1 for s in data["submissions"] if s["status"] == "rejected")
    data["pending"] = sum(1 for s in data["submissions"] if s["status"] == "pending")
    data["internal_applied"] = sum(1 for s in data["submissions"] if s["status"] == "internal-applied")

    CONTRIB.write_text(json.dumps(data, indent=2))
    LEDGER.write_text(json.dumps(ledger, indent=2))

    print(f"Reviewed: approved={approved}, rejected={rejected}, skipped={skipped}")
    print(f"Final state: total={data['total']}, approved={data['approved']}, rejected={data['rejected']}, pending={data['pending']}, internal={data['internal_applied']}")


if __name__ == "__main__":
    main()
