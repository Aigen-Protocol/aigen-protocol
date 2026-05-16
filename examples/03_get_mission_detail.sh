#!/usr/bin/env bash
# Fetch full detail of one mission: description, exact reward, verification rule,
# and any submissions already received.

set -euo pipefail
BASE="${BASE:-https://cryptogenesis.duckdns.org}"
MISSION_ID="${1:-mis_eb8da2d8cf02}"  # pick an id from 02_list_open_missions.sh

echo "→ GET $BASE/api/missions/$MISSION_ID"
curl -fsS "$BASE/api/missions/$MISSION_ID" | jq .

# Key fields to read before submitting:
#   reward.currency / reward.amount   — what you'll be paid in (USDC micros, AIGEN, ETH wei)
#   reward.deposit_confirmed_at       — if null, the mission isn't funded yet
#   verification_type + verification_params — read these carefully; they define what counts as "valid"
#   submissions[]                     — what others have already submitted
#   deadline                          — submit before this timestamp
