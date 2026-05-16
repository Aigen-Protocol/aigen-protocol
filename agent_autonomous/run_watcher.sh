#!/bin/bash
# AIGEN-WATCHER — lightweight observation agent, runs every 5 min.
# Cheap (Sonnet), short (<5s), no commits.
# Output: state/watcher_last_seen.json + maybe state/wake_builder

set -e
cd /home/luna/crypto-genesis/aigen/agent_autonomous

LOGFILE="state/watcher.log"
NOW_ISO=$(date -u +%FT%TZ)

# Kill switch + degraded mode honored
[ -f state/kill_switch ] && { echo "[$NOW_ISO] kill_switch" >> $LOGFILE; exit 0; }
[ -f state/watch_only_until ] && {
    UNTIL=$(cat state/watch_only_until)
    NOW_E=$(date -u +%s); UNTIL_E=$(date -d "$UNTIL" +%s 2>/dev/null || echo 0)
    [ "$NOW_E" -lt "$UNTIL_E" ] && { echo "[$NOW_ISO] degraded mode" >> $LOGFILE; exit 0; }
}

# Quick dashboard refresh (lighter than the Builder version — only what watcher needs)
python3 - > state/watcher_dashboard.json 2>>"$LOGFILE" <<'PYEOF'
import json, time, urllib.request, subprocess
out = {"ts": time.strftime("%FT%TZ", time.gmtime())}
try:
    res = subprocess.run(["sudo","tail","-50","/var/log/nginx/access.log"],
        capture_output=True, text=True, timeout=3)
    ips = set(); paths = {}
    for line in res.stdout.split("\n"):
        parts = line.split()
        if len(parts) > 6:
            ips.add(parts[0])
            paths[parts[6]] = paths.get(parts[6], 0) + 1
    out["recent_ips"] = sorted(ips)
    out["top_paths"] = sorted(paths.items(), key=lambda x: -x[1])[:5]
except Exception as e:
    out["nginx_err"] = str(e)[:80]
try:
    out["gh_notif_count"] = len(json.loads(subprocess.run(
        ["gh","api","notifications","--jq","[.[]]"],
        capture_output=True, text=True, timeout=4).stdout or "[]"))
except Exception:
    out["gh_notif_count"] = "?"
try:
    res = subprocess.run(["gh","api","repos/Aigen-Protocol/aigen-protocol",
        "--jq","{stars: .stargazers_count, forks: .forks_count}"],
        capture_output=True, text=True, timeout=4)
    out["repo"] = json.loads(res.stdout)
except Exception: pass
print(json.dumps(out, indent=2))
PYEOF

# Invoke watcher (Sonnet)
PROMPT="It's $NOW_ISO. You are AIGEN-WATCHER. Read state/watcher_dashboard.json and state/watcher_last_seen.json. Decide: anything NEW and INTERESTING since last snapshot? Write the new snapshot to state/watcher_last_seen.json. If new+interesting, also write state/wake_builder with a 1-line reason. Otherwise log 'calme' to state/watcher.log. Output final JSON line."

claude --print \
    --append-system-prompt "$(cat watcher_prompt.md)" \
    --add-dir /home/luna/crypto-genesis/aigen \
    --dangerously-skip-permissions \
    --model sonnet \
    --output-format json \
    "$PROMPT" \
    > state/.watcher_last_response.json \
    2>> "$LOGFILE" || {
    echo "[$NOW_ISO] watcher failed exit=$?" >> "$LOGFILE"
    exit 1
}

# Log result
COST=$(jq -r '.total_cost_usd // 0' state/.watcher_last_response.json 2>/dev/null || echo 0)
RESULT=$(jq -r '.result // ""' state/.watcher_last_response.json 2>/dev/null | head -c 200)
echo "[$NOW_ISO] watcher cost=\$$COST result=$RESULT" >> "$LOGFILE"

# Roll watcher.log if too big (>500KB)
if [ -f "$LOGFILE" ] && [ "$(stat -c%s $LOGFILE)" -gt 500000 ]; then
    mv "$LOGFILE" "${LOGFILE}.old"
fi
