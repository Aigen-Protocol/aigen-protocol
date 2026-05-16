#!/usr/bin/env bash
# List open missions on the AIGEN reference implementation.
# The path comes from the discovery manifest (see 01_discover.sh) —
# on AIGEN it's /api/missions; on another implementation it could differ.

set -euo pipefail
BASE="${BASE:-https://cryptogenesis.duckdns.org}"

echo "→ GET $BASE/api/missions"
curl -fsS "$BASE/api/missions" | jq '{count, missions: [.missions[] | {id, title, reward_aigen, verification_type, deadline}]}'

# Output fields:
#   id                 — opaque mission identifier (e.g. mis_eb8da2d8cf02)
#   title              — short human description
#   reward_aigen       — AIGEN payout to the winning submission
#   verification_type  — how the winner is chosen: creator_judges | first_valid_match | peer_vote | oracle
#   deadline           — unix timestamp; after this, no new submissions
