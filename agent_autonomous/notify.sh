#!/bin/bash
# Push notification helper for AIGEN autopilot.
# Sends via Telegram Bot API (@Satoshi_ClubBot → ImanaBTC chat).
#
# Usage:
#   notify.sh "Title" "Body" [priority]
#   priority: low | default | high | urgent (mapped to Telegram silent + emoji prefix)
#
# Or via env:
#   NOTIFY_TITLE="..." NOTIFY_BODY="..." NOTIFY_PRIORITY=high notify.sh

CREDS=/home/luna/crypto-genesis/aigen/agent_autonomous/state/.telegram_creds
if [ ! -f "$CREDS" ]; then
    echo "no telegram creds at $CREDS" >&2
    exit 1
fi
source "$CREDS"

TITLE="${1:-${NOTIFY_TITLE:-AIGEN autopilot}}"
BODY="${2:-${NOTIFY_BODY:-(no body)}}"
PRIORITY="${3:-${NOTIFY_PRIORITY:-default}}"

case "$PRIORITY" in
    urgent)  PREFIX="🚨"; SILENT="false" ;;
    high)    PREFIX="🔥"; SILENT="false" ;;
    low)     PREFIX="ℹ️"; SILENT="true"  ;;
    *)       PREFIX="🤖"; SILENT="false" ;;
esac

# Telegram message: title bold, body below, with link to dashboard
MSG="${PREFIX} <b>${TITLE}</b>
${BODY}

<a href=\"https://cryptogenesis.duckdns.org/agent\">→ dashboard</a>"

curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
    -d chat_id="${TELEGRAM_CHAT_ID}" \
    -d parse_mode="HTML" \
    -d disable_web_page_preview="true" \
    -d disable_notification="${SILENT}" \
    --data-urlencode text="${MSG}" \
    > /dev/null
