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
python3 dashboard_refresh.py > state/dashboard.json 2>>"$LOGFILE"

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

# Operator overrides (read at every invocation — added 2026-05-22)
# Operator can exclude/add/comment/approve tasks via /agent dashboard. JSON at state/operator_overrides.json.
OVERRIDES_JSON=""
if [ -f state/operator_overrides.json ]; then
    OVERRIDES_JSON=$(cat state/operator_overrides.json 2>/dev/null)
fi

PROMPT="It'\''s $NOW_ISO. You are AIGEN-AUTOPILOT, invoked by cron.

ROADMAP — Read state/roadmap.json FIRST. Contains:
  - standing: routine duties (github PRs, DMs, oracle missions, stay-active) — DO THESE EVERY CYCLE, mark .last_done=$NOW_ISO
  - missions: discrete operator-tracked goals — work on TOP 5 active
  - completed_today: append what you finished this cycle

CRITICAL RULE — operator_blocked field per mission:
  - operator_blocked=true ONLY IF you genuinely cannot proceed without operator answer (decision, credentials, browser-only). Examples: 'Accept lobsterai agent? need decision', 'Which channel for outreach?'
  - operator_blocked=false (default) → JUST DO IT YOURSELF. Examples: review PR, respond to issue, judge oracle mission, post chat, send queued DM if drafted.
  - When in doubt, set operator_blocked=false. Operator complained you ask too much.

OPERATOR OVERRIDES — $OVERRIDES_JSON
  - excluded_task_ids → REMOVE matching items
  - added_tasks → operator-created missions at top priority
  - comments {id: text} → operator notes per task — surface + respect
  - approved_task_ids → boost priority

READ also: chat.jsonl, always_available_work.md, focus.md, journal.md, lessons.md, dashboard.json, outreach_status.json.

EXECUTE & EVOLVE ROADMAP:
1. Pick highest-leverage action (standing duty first; if all standing done recently <2h, work on active mission).
2. Execute it.
3. UPDATE state/roadmap.json:
   - standing[i].last_done = NOW for executed standing duty
   - completed_today += [{id, title, done_ts, evidence}] for what you finished
   - missions[i].status = "done" → remove from missions[], it auto-archives via completed_today
   - Add NEW missions you identified (don'\''t hesitate: short title + priority + next_step)
   - Update next_step / status for missions in_progress
4. Post chat, append journal, exit.
ROADMAP EVOLVES: keep missions[] forward-looking (max 10 active). Completed missions go to completed_today, then archived nightly to completed_history.

If AIGEN_DEGRADED_MODE=1 → observation-only."

# stdout (JSON) → .last_response.json
# stderr (warnings) → log
# === GUARD (added 2026-06-01): protect live core code + clean garbage on ANY exit ===
GUARD_CORE="/home/luna/crypto-genesis/aigen/missions.py /home/luna/crypto-genesis/aigen/oabp_verifier.py /home/luna/crypto-genesis/token-scanner/scanner.py"
mkdir -p state/code_snapshot 2>/dev/null || true
for _gf in $GUARD_CORE; do cp -p "$_gf" "state/code_snapshot/$(basename "$_gf").pre" 2>/dev/null || true; done
_guard_run() {
    set +e
    for _gf in $GUARD_CORE; do
        _snap="state/code_snapshot/$(basename "$_gf").pre"
        [ -f "$_snap" ] || continue
        cmp -s "$_gf" "$_snap" && continue
        _bad=0
        python3 -m py_compile "$_gf" 2>/dev/null || _bad=1
        case "$(basename "$_gf")" in
            missions.py)      grep -q "anti-farm guards" "$_gf" || _bad=1 ;;
            oabp_verifier.py) grep -q "verify_safety_review" "$_gf" || _bad=1 ;;
        esac
        if [ "$_bad" = "1" ]; then
            cp -p "$_snap" "$_gf" 2>/dev/null
            echo "[GUARD] reverted unsafe change to $_gf; arming kill_switch" >> "$LOGFILE"
            echo "GUARD halt $(date -u +%FT%TZ): unsafe core-code change to $(basename "$_gf") auto-reverted" > state/kill_switch
        fi
    done
    find . -maxdepth 1 -type f \( -name '*[{}]*' -o -name '*:' \) 2>/dev/null | while read -r _g; do
        rm -f -- "$_g" 2>/dev/null && echo "[GUARD] removed garbage file: $_g" >> "$LOGFILE"
    done
}
trap _guard_run EXIT

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
