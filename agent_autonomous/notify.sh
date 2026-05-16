#!/bin/bash
# Push notification helper for AIGEN autopilot.
# Usage:
#   notify.sh "Title" "Body" [priority]
#   priority: min | low | default | high | urgent
#
# Or via env:
#   NOTIFY_TITLE="..." NOTIFY_BODY="..." NOTIFY_PRIORITY=high notify.sh
#
# Sends via ntfy.sh to the topic in state/.ntfy_topic.

TOPIC=$(cat /home/luna/crypto-genesis/aigen/agent_autonomous/state/.ntfy_topic 2>/dev/null)
[ -z "$TOPIC" ] && { echo "no ntfy topic configured" >&2; exit 1; }

TITLE="${1:-${NOTIFY_TITLE:-AIGEN autopilot}}"
BODY="${2:-${NOTIFY_BODY:-(no body)}}"
PRIORITY="${3:-${NOTIFY_PRIORITY:-default}}"

# Click action: open the dashboard
CLICK="https://cryptogenesis.duckdns.org/agent"

curl -s -X POST "https://ntfy.sh/$TOPIC" \
    -H "Title: $TITLE" \
    -H "Priority: $PRIORITY" \
    -H "Tags: robot" \
    -H "Click: $CLICK" \
    -d "$BODY" > /dev/null
