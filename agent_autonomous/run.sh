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

# --- SAFETY: degraded mode (watch-only until timestamp) ---
if [ -f state/watch_only_until ]; then
    UNTIL=$(cat state/watch_only_until | head -1)
    NOW_EPOCH=$(date -u +%s)
    UNTIL_EPOCH=$(date -d "$UNTIL" +%s 2>/dev/null || echo 0)
    if [ "$NOW_EPOCH" -lt "$UNTIL_EPOCH" ]; then
        export AIGEN_DEGRADED_MODE=1
        echo "[SAFETY] degraded mode active until $UNTIL — agent restricted to observation" >> "$LOGFILE"
    else
        rm -f state/watch_only_until
        echo "[SAFETY] degraded mode expired ($UNTIL passed), removed" >> "$LOGFILE"
    fi
fi

# --- TRIGGER: read + delete trigger_now (re-arms claude-autopilot.path) ---
TRIGGER_REASON=""
if [ -f state/trigger_now ]; then
    TRIGGER_REASON=$(cat state/trigger_now)
    echo "[TRIGGER] fired by webhook: $TRIGGER_REASON" >> "$LOGFILE"
    rm -f state/trigger_now
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
import json, time, urllib.request, subprocess, os
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
try:
    res = subprocess.run(
        ["gh","api","notifications","--jq",
         "[.[] | {repo: .repository.full_name, type: .subject.type, title: .subject.title, url: .subject.url, reason: .reason, updated_at: .updated_at, unread: .unread}]"],
        capture_output=True, text=True, timeout=10)
    out["github_notifications"] = json.loads(res.stdout) if res.stdout.strip() else []
    out["github_notifications_count"] = len(out["github_notifications"])
except Exception as e:
    out["github_notifications_error"] = str(e)
try:
    if os.path.exists("state/triggers.log"):
        with open("state/triggers.log") as f:
            lines = f.readlines()
        out["recent_webhook_triggers"] = [l.strip() for l in lines[-5:]]
except Exception:
    pass

# Fresh context: pull a few high-leverage external snapshots (rate-limited)
fresh = {}
try:
    # Our own GitHub repo: stars + open issues (cheap, single API call)
    res = subprocess.run(["gh", "api", "repos/Aigen-Protocol/aigen-protocol",
                          "--jq", "{stars: .stargazers_count, forks: .forks_count, open_issues: .open_issues_count, watchers: .subscribers_count}"],
                         capture_output=True, text=True, timeout=8)
    if res.returncode == 0:
        fresh["repo_stats"] = json.loads(res.stdout)
except Exception as e:
    fresh["repo_stats_err"] = str(e)[:120]
try:
    # Recent commits to awesome-mcp-servers (signal: who's submitting today)
    res = subprocess.run(["gh", "api", "repos/punkpeye/awesome-mcp-servers/commits",
                          "--jq", "[.[0:5] | .[] | {sha: .sha[0:8], msg: .commit.message[0:80], when: .commit.author.date}]"],
                         capture_output=True, text=True, timeout=8)
    if res.returncode == 0:
        fresh["awesome_mcp_recent"] = json.loads(res.stdout)
except Exception as e:
    fresh["awesome_mcp_err"] = str(e)[:120]
try:
    # HN top 30 stories — filter for agent / mcp / bounty keywords
    r = urllib.request.urlopen("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=6)
    top_ids = json.loads(r.read())[:30]
    hits = []
    for sid in top_ids:
        try:
            rs = urllib.request.urlopen(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=4)
            st = json.loads(rs.read())
            title = (st.get("title", "") or "").lower()
            if any(k in title for k in ["agent", "mcp", "anthropic", "bounty", "claude", "open ai", "openai", "model context"]):
                hits.append({"id": sid, "title": st.get("title"), "score": st.get("score"),
                             "url": st.get("url"), "comments": st.get("descendants", 0)})
                if len(hits) >= 5: break
        except Exception:
            continue
    fresh["hn_relevant"] = hits
except Exception as e:
    fresh["hn_err"] = str(e)[:120]
out["fresh_context"] = fresh
try:
    import imaplib, email as email_mod
    from email.header import decode_header
    creds = open("/home/luna/crypto-genesis/credentials/zoho_mail.txt").read()
    user = "Cryptogen@zohomail.eu"
    pw = creds.split("Password:")[1].split("\n")[0].strip()
    M = imaplib.IMAP4_SSL("imap.zoho.eu", 993)
    M.login(user, pw)
    M.select("INBOX")
    # Look at the last 14 days of emails
    typ, data = M.search(None, '(SINCE "01-May-2026")')
    msg_ids = data[0].split()[-15:]
    inbox = []
    for mid in msg_ids:
        typ, msg_data = M.fetch(mid, '(BODY.PEEK[HEADER])')
        if typ != "OK": continue
        msg = email_mod.message_from_bytes(msg_data[0][1])
        subject = msg.get("Subject", "")
        try:
            decoded = decode_header(subject)
            subject = "".join(s.decode(c or "utf-8") if isinstance(s, bytes) else s for s, c in decoded)
        except Exception:
            pass
        inbox.append({
            "from": msg.get("From", ""),
            "subject": subject[:140],
            "date": msg.get("Date", ""),
            "uid": mid.decode() if isinstance(mid, bytes) else str(mid),
        })
    out["inbox_recent"] = inbox[-15:]
    out["inbox_count"] = len(msg_ids)
    M.close(); M.logout()
except Exception as e:
    out["inbox_error"] = str(e)[:200]
print(json.dumps(out, indent=2))
PYEOF

# --- COST-AWARE: pick model based on today's spend ---
# Default: opus (best). If today's api-equiv > $30 OR degraded mode: sonnet (5× cheaper).
MODEL_FLAG=""
TODAY_SO_FAR=$(jq -r .today_spent_usd state/budget.json)
if (( $(echo "$TODAY_SO_FAR > 30" | bc -l) )) || [ -n "$AIGEN_DEGRADED_MODE" ]; then
    MODEL_FLAG="--model sonnet"
    echo "[COST] using sonnet (today=\$$TODAY_SO_FAR, degraded=${AIGEN_DEGRADED_MODE:-0})" >> "$LOGFILE"
fi

# --- INVOKE Claude ---
echo "[CLAUDE] invoking with --dangerously-skip-permissions $MODEL_FLAG --output-format json..." >> "$LOGFILE"

PROMPT="It's $NOW_ISO. You are AIGEN-AUTOPILOT, invoked by cron. Read state files (chat.jsonl FIRST, then always_available_work.md, focus.md, journal.md, lessons.md, dashboard.json, outreach_status.json). If degraded mode env var AIGEN_DEGRADED_MODE=1 is set, observation-only. Pick highest-leverage action per your system prompt, execute it, update tasks.json + post to chat + append to journal, exit."

# stdout (JSON) → .last_response.json
# stderr (warnings) → log
claude --print \
    --append-system-prompt "$(cat system_prompt.md)" \
    --add-dir /home/luna/crypto-genesis/aigen \
    --dangerously-skip-permissions \
    $MODEL_FLAG \
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
