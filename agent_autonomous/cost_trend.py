#!/usr/bin/env python3
"""
AIGEN-AUTOPILOT cost trend analysis (backlog item E.1).

Reads logs/YYYY-MM-DD.log files, extracts [CLAUDE] cost= lines,
groups by day, computes rolling 7d avg (excluding today), and
flags elevated/alarm conditions per system_prompt.md thresholds.

Writes state/cost_trend.json. Read-only against logs/, idempotent.

Status levels (today_actual = sum so far; today_projected = scaled to 24h):
  ok        — today_projected <= 1.0x rolling_7d_avg
  elevated  — 1.0x < today_projected <= 1.5x avg  OR  today_actual > $40
  alarm     — today_projected > 1.5x avg          OR  today_actual > $80
  kill_zone — today_actual > $150 (system_prompt kill threshold)

Designed to be:
  - safe to run any time (read-only on logs/, atomic write on state/)
  - useful for forks (referenced from docs/SECOND_IMPLEMENTATION.md)
"""
import glob
import json
import os
import re
import tempfile
import time

LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")
OUT_PATH = os.path.join(os.path.dirname(__file__), "state", "cost_trend.json")

COST_RE = re.compile(r"^\[CLAUDE\] cost=\$([0-9]+\.?[0-9]*) duration_ms=([0-9]+) turns=([0-9]+)")
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\.log$")


def parse_day(path):
    total = 0.0
    count = 0
    max_run = 0.0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = COST_RE.match(line)
            if not m:
                continue
            c = float(m.group(1))
            total += c
            count += 1
            if c > max_run:
                max_run = c
    avg_run = total / count if count else 0.0
    return {"total": round(total, 4), "count": count,
            "avg_per_run": round(avg_run, 4), "max_run": round(max_run, 4)}


def main():
    today = time.strftime("%Y-%m-%d", time.gmtime())
    by_day = {}
    for path in sorted(glob.glob(os.path.join(LOGS_DIR, "*.log"))):
        m = DATE_RE.search(path)
        if not m:
            continue
        date = m.group(1)
        by_day[date] = parse_day(path)

    # Rolling avg from last 7 COMPLETE days (not today)
    complete = [(d, v) for d, v in sorted(by_day.items()) if d != today]
    last7 = complete[-7:]
    if last7:
        avg_7d = sum(v["total"] for _, v in last7) / len(last7)
    else:
        avg_7d = 0.0

    today_actual = by_day.get(today, {}).get("total", 0.0)
    today_count = by_day.get(today, {}).get("count", 0)

    # Projection: scale today's spend to 24h based on UTC hour-of-day fraction.
    # If we're 3h into the day with $10, projected = $10 * 24/3 = $80.
    # Floor at 1.0h to avoid divide-by-zero or wild early-morning extrapolation.
    now = time.gmtime()
    hours_elapsed = max(1.0, now.tm_hour + now.tm_min / 60.0)
    today_projected = today_actual * 24.0 / hours_elapsed

    # Status thresholds — see system_prompt.md "Cost-aware mode" section
    KILL_HARD = 150.0
    ALARM_ABS = 80.0
    ELEVATED_ABS = 40.0
    ALARM_RATIO = 1.5
    ELEVATED_RATIO = 1.0

    status = "ok"
    reasons = []
    if today_actual > KILL_HARD:
        status = "kill_zone"
        reasons.append(f"today_actual ${today_actual:.2f} > kill threshold ${KILL_HARD:.0f}")
    elif today_actual > ALARM_ABS or today_projected > ALARM_RATIO * avg_7d:
        status = "alarm"
        if today_actual > ALARM_ABS:
            reasons.append(f"today_actual ${today_actual:.2f} > alarm threshold ${ALARM_ABS:.0f}")
        if avg_7d > 0 and today_projected > ALARM_RATIO * avg_7d:
            reasons.append(f"today_projected ${today_projected:.2f} > {ALARM_RATIO}x 7d avg ${avg_7d:.2f}")
    elif today_actual > ELEVATED_ABS or (avg_7d > 0 and today_projected > ELEVATED_RATIO * avg_7d):
        status = "elevated"
        if today_actual > ELEVATED_ABS:
            reasons.append(f"today_actual ${today_actual:.2f} > elevated threshold ${ELEVATED_ABS:.0f}")
        if avg_7d > 0 and today_projected > ELEVATED_RATIO * avg_7d:
            reasons.append(f"today_projected ${today_projected:.2f} > 7d avg ${avg_7d:.2f}")

    out = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "today": today,
        "today_hours_elapsed": round(hours_elapsed, 2),
        "today_actual_usd": round(today_actual, 4),
        "today_count": today_count,
        "today_projected_usd": round(today_projected, 4),
        "rolling_7d_avg_usd": round(avg_7d, 4),
        "rolling_7d_days_used": len(last7),
        "status": status,
        "reasons": reasons,
        "thresholds": {
            "kill_hard": KILL_HARD,
            "alarm_abs": ALARM_ABS,
            "elevated_abs": ELEVATED_ABS,
            "alarm_ratio_vs_7d_avg": ALARM_RATIO,
            "elevated_ratio_vs_7d_avg": ELEVATED_RATIO,
        },
        "history": {d: v for d, v in sorted(by_day.items())},
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False,
                                     dir=os.path.dirname(OUT_PATH),
                                     suffix=".tmp") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        tmp = f.name
    os.rename(tmp, OUT_PATH)

    # Stdout summary for cron-line readability
    print(f"status={status} today=${today_actual:.2f}({today_count} runs) "
          f"projected=${today_projected:.2f} avg7d=${avg_7d:.2f}")
    if reasons:
        for r in reasons:
            print(f"  - {r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
