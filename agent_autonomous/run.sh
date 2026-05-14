#!/bin/bash
# AIGEN-AUTOPILOT — autonomous agent runner.
# Called by systemd timer / cron every 4h.
# Each invocation: 1 decision, 1 action, log, exit.

set -e
cd /home/luna/crypto-genesis/aigen/agent_autonomous

LOGFILE="logs/$(date -u +%F).log"
TODAY=$(date -u +%F)
NOW_ISO=$(date -u +%FT%TZ)

# Append marker to logfile
{
  echo ""
  echo "=========================================="
  echo "[$NOW_ISO] AIGEN-AUTOPILOT invocation start"
  echo "=========================================="
} >> "$LOGFILE"

# --- SAFETY: kill switch ---
if [ -f state/kill_switch ]; then
    echo "[SAFETY] kill_switch present — exiting" >> "$LOGFILE"
    exit 0
fi

# --- TRACKING: api-equivalent value (NOT real cost on Max plan) ---
# We're on Claude Max — these are pay-as-you-go EQUIVALENT dollars,
# they consume the Max message-quota window not actual $.
LAST_DAY=$(jq -r .today state/budget.json)
TODAY_SPENT=$(jq -r .today_spent_usd state/budget.json)

if [ "$LAST_DAY" != "$TODAY" ]; then
    echo "[TRACKING] new day, resetting today_spent (was api-equivalent \$$TODAY_SPENT on $LAST_DAY)" >> "$LOGFILE"
    TMP=$(mktemp)
    jq --arg t "$TODAY" '.today=$t | .today_spent_usd=0' state/budget.json > "$TMP" && mv "$TMP" state/budget.json
fi

# kill_switch is the only hard stop. No $-cap on Max.

# --- REFRESH dashboard ---
echo "[STATE] refreshing dashboard..." >> "$LOGFILE"
python3 << 'PYEOF' > state/dashboard.json 2>>"$LOGFILE"
import json, time, urllib.request, subprocess
out = {
    "_note": "Refreshed by run.sh",
    "last_refresh_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
try:
    r = urllib.request.urlopen("http://127.0.0.1:4444/missions/stats", timeout=5)
    out["missions"] = json.loads(r.read())
except Exception as e:
    out["missions_error"] = str(e)
try:
    body = json.dumps({"jsonrpc":"2.0","method":"eth_call","params":[
        {"to":"0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
         "data":"0x70a08231000000000000000000000000Da429f2034b62b8722713873dE3C045eec390d8F"}, "latest"],
        "id":1}).encode()
    req = urllib.request.Request("https://mainnet.base.org", method="POST", data=body,
                                 headers={"Content-Type":"application/json","User-Agent":"agent/1.0"})
    with urllib.request.urlopen(req, timeout=5) as r:
        d = json.loads(r.read())
    out["treasury_usdc"] = int(d.get("result","0x0"),16)/1e6
except Exception as e:
    out["treasury_error"] = str(e)
try:
    res = subprocess.run(["sudo","tail","-100","/var/log/nginx/access.log"],
                         capture_output=True, text=True, timeout=5)
    paths = {}; ips = set()
    for line in res.stdout.split("\n"):
        parts = line.split()
        if len(parts) > 6:
            paths[parts[6]] = paths.get(parts[6], 0) + 1
            ips.add(parts[0])
    out["recent_top_paths"] = sorted(paths.items(), key=lambda x: -x[1])[:8]
    out["recent_unique_ips"] = len(ips)
    out["hustlerops_recent"] = "89.213.118.44" in ips
except Exception as e:
    out["nginx_error"] = str(e)
try:
    out["recent_commits"] = subprocess.run(
        ["git","-C","/home/luna/crypto-genesis/aigen","log","--oneline","-5"],
        capture_output=True, text=True, timeout=5).stdout.strip().split("\n")
except Exception as e:
    out["git_error"] = str(e)
print(json.dumps(out, indent=2))
PYEOF

# --- INVOKE Claude ---
echo "[CLAUDE] invoking with --dangerously-skip-permissions and --output-format json..." >> "$LOGFILE"

PROMPT="It's $NOW_ISO. You are AIGEN-AUTOPILOT, invoked by cron. Read state files (focus.md, journal.md, lessons.md, dashboard.json), pick the highest-leverage action right now per your system prompt, execute it, append to journal.md, exit."

# stdout (JSON) → .last_response.json
# stderr (warnings) → log
claude --print \
    --append-system-prompt "$(cat system_prompt.md)" \
    --add-dir /home/luna/crypto-genesis/aigen \
    --dangerously-skip-permissions \
    --output-format json \
    "$PROMPT" \
    > .last_response.json \
    2>> "$LOGFILE" || {
        EXIT_CODE=$?
        echo "[CLAUDE] invocation failed with exit $EXIT_CODE" >> "$LOGFILE"
        TMP=$(mktemp)
        jq '.lifetime_invocations += 1' state/budget.json > "$TMP" && mv "$TMP" state/budget.json
        exit $EXIT_CODE
    }

# --- BUDGET update ---
if [ -s .last_response.json ]; then
    COST=$(jq -r '.total_cost_usd // 0' .last_response.json 2>/dev/null || echo "0")
    RESULT=$(jq -r '.result // ""' .last_response.json 2>/dev/null | head -c 500)
    DURATION=$(jq -r '.duration_ms // 0' .last_response.json 2>/dev/null)
    NUM_TURNS=$(jq -r '.num_turns // 0' .last_response.json 2>/dev/null)

    {
      echo "[CLAUDE] cost=\$$COST duration_ms=$DURATION turns=$NUM_TURNS"
      echo "[CLAUDE] result preview:"
      echo "$RESULT"
    } >> "$LOGFILE"
else
    echo "[CLAUDE] no response captured (.last_response.json empty)" >> "$LOGFILE"
    COST="0"
fi

TMP=$(mktemp)
jq --arg c "$COST" '.today_spent_usd += ($c | tonumber)
                    | .lifetime_spent_usd += ($c | tonumber)
                    | .lifetime_invocations += 1' state/budget.json > "$TMP" && mv "$TMP" state/budget.json

NEW_TODAY=$(jq -r .today_spent_usd state/budget.json)
LIFETIME=$(jq -r .lifetime_invocations state/budget.json)
echo "[TRACKING] today api-equivalent total: \$$NEW_TODAY (lifetime invocations: $LIFETIME)" >> "$LOGFILE"

QUEUE_COUNT=$(ls approval_queue/*.md 2>/dev/null | wc -l)
if [ "$QUEUE_COUNT" -gt 0 ]; then
    echo "[QUEUE] $QUEUE_COUNT items waiting for human approval" >> "$LOGFILE"
fi

NOW_END=$(date -u +%FT%TZ)
echo "[$NOW_END] invocation done" >> "$LOGFILE"
