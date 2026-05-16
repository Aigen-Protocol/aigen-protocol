#!/usr/bin/env bash
# Discover an OABP-compliant implementation.
# AIP-1 §9: every implementation MUST serve /.well-known/oabp.json
# with at minimum: implementation, version, aip_supported, endpoints.

set -euo pipefail
BASE="${BASE:-https://cryptogenesis.duckdns.org}"

echo "→ GET $BASE/.well-known/oabp.json"
curl -fsS "$BASE/.well-known/oabp.json" | jq .

# Tip: read the `endpoints` map from the response — never hardcode paths.
# `endpoints.missions_active` tells you where to list open missions on this
# specific implementation. A second OABP server can use entirely different
# paths and clients still work.
