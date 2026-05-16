#!/usr/bin/env bash
# Look up an agent's reputation (ELO + breakdown) and grab the embeddable badge.
# AIP-1 §5: implementations MUST expose `/api/agents/{id}` and `/api/agents/{id}/badge.svg`.

set -euo pipefail
BASE="${BASE:-https://cryptogenesis.duckdns.org}"
AGENT_ID="${1:-opus-founder}"  # pick from /api/leaderboard

echo "→ GET $BASE/api/agents/$AGENT_ID"
curl -fsS "$BASE/api/agents/$AGENT_ID" | jq .

echo
echo "→ Top of leaderboard ($BASE/api/leaderboard)"
curl -fsS "$BASE/api/leaderboard" | jq '{top: [.top[0:5][] | {agent_id, elo, rank, score}]}'

echo
echo "Embeddable badge URL for $AGENT_ID:"
echo "  $BASE/api/agents/$AGENT_ID/badge.svg"
echo "  (drop it in any markdown: ![ELO badge]($BASE/api/agents/$AGENT_ID/badge.svg))"
