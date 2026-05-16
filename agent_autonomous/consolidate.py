#!/usr/bin/env python3
"""Memory consolidation — runs daily via cron or manually.

Triggers:
- Friday 18:00 UTC: archive past week's journal + emit weekly_digest
- Always: dedupe lessons.md (remove exact duplicates)
- If journal > 200KB: emergency archive (truncate to last 7 days)

Idempotent: safe to run multiple times.
"""

import os
import re
import sys
import time
import shutil
import hashlib
from datetime import datetime, timedelta, timezone

STATE = "/home/luna/crypto-genesis/aigen/agent_autonomous/state"
ARCHIVE = "/home/luna/crypto-genesis/aigen/agent_autonomous/journal_archive"
JOURNAL = f"{STATE}/journal.md"
LESSONS = f"{STATE}/lessons.md"
PUBLIC_DIGESTS = "/home/luna/crypto-genesis/aigen/reports"

os.makedirs(ARCHIVE, exist_ok=True)
os.makedirs(PUBLIC_DIGESTS, exist_ok=True)


def iso_week_label(dt: datetime) -> str:
    iso_year, iso_week, _ = dt.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def parse_entries(content: str):
    """Yield (ts_str, datetime, full_block) for each ## entry."""
    pattern = re.compile(r'^(## (\d{4}-\d{2}-\d{2}T[\d:]+Z)[^\n]*\n.*?)(?=^## \d{4}-|\Z)',
                         re.MULTILINE | re.DOTALL)
    for m in pattern.finditer(content):
        ts_str = m.group(2)
        try:
            ts = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        yield ts_str, ts, m.group(1)


def consolidate_journal(force_emergency=False):
    if not os.path.exists(JOURNAL):
        return
    size = os.path.getsize(JOURNAL)
    with open(JOURNAL) as f:
        raw = f.read()

    # Split header from entries
    header_end = raw.find("\n---\n")
    if header_end == -1:
        header = raw.split("\n## ")[0]
        body = "## " + raw.split("\n## ", 1)[1] if "\n## " in raw else ""
    else:
        header = raw[:header_end + 5]
        body = raw[header_end + 5:]

    entries = list(parse_entries(body))
    if not entries:
        print("no entries to consolidate")
        return

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)

    if not force_emergency and size < 200_000 and now.weekday() != 4:  # Friday=4
        print(f"journal size {size} bytes, not Friday, skipping")
        return

    keep = [e for e in entries if e[1] >= cutoff]
    archive_us = [e for e in entries if e[1] < cutoff]

    if not archive_us:
        print("nothing older than 7 days, skipping")
        return

    # Group archived by ISO week
    by_week = {}
    for ts_str, ts, block in archive_us:
        wk = iso_week_label(ts)
        by_week.setdefault(wk, []).append(block)

    for wk, blocks in by_week.items():
        archive_file = f"{ARCHIVE}/{wk}.md"
        with open(archive_file, "a") as f:
            f.write("\n\n".join(blocks))
            f.write("\n\n---\n\n")
        print(f"archived {len(blocks)} entries to {archive_file}")

    # Rewrite journal with header + recent entries only
    new_body = "\n\n".join(b for _, _, b in keep)
    with open(JOURNAL + ".tmp", "w") as f:
        f.write(header + new_body)
        if not new_body.endswith("\n"):
            f.write("\n")
    os.rename(JOURNAL + ".tmp", JOURNAL)
    print(f"journal truncated to {len(keep)} recent entries ({os.path.getsize(JOURNAL)} bytes)")


def emit_weekly_digest():
    """Generate a public weekly report at /reports/{week}.md.

    Pulls from: journal entries this week, commits this week, chat highlights,
    backlog completions, outreach activity.
    """
    now = datetime.now(timezone.utc)
    # Last completed Friday-to-Friday week
    wk = iso_week_label(now)
    digest_path = f"{PUBLIC_DIGESTS}/{wk}.md"
    if os.path.exists(digest_path):
        # Update it (overwrite)
        pass

    # Parse this week's entries
    with open(JOURNAL) as f:
        body = f.read()
    week_start = now - timedelta(days=now.weekday() + 1) if now.weekday() < 4 else now - timedelta(days=now.weekday() - 4)
    week_entries = []
    for ts_str, ts, block in parse_entries(body):
        if ts >= week_start:
            week_entries.append((ts_str, ts, block))

    # Categorize entries
    classifier = {"🛡": "infra", "📜": "doc", "📤": "submit", "💬": "outreach",
                  "🧠": "learn", "📋": "queue", "📡": "signal", "🚀": "commit",
                  "👀": "watch", "⚙️": "other"}
    cats = {v: 0 for v in classifier.values()}
    cats["other"] = 0
    for ts_str, ts, block in week_entries:
        for emoji, cat in classifier.items():
            if emoji in block:
                cats[cat] = cats.get(cat, 0) + 1
                break
        else:
            cats["other"] += 1

    # Commits this week
    import subprocess
    cmd = ["git", "-C", "/home/luna/crypto-genesis/aigen", "log",
           f"--since={week_start.strftime('%Y-%m-%d')}", "--oneline"]
    commits = subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip().split("\n")
    commits = [c for c in commits if c.strip()]

    # Backlog completions
    backlog_path = f"{STATE}/always_available_work.md"
    completed = []
    if os.path.exists(backlog_path):
        with open(backlog_path) as f:
            for line in f:
                if line.startswith("- [x]") or line.startswith("- [~]"):
                    completed.append(line.strip())

    # Generate digest
    content = f"""---
title: "Weekly digest — {wk}"
date: {now.strftime('%Y-%m-%d')}
week: {wk}
---

# Week {wk} — what the autopilot shipped

**Period:** {week_start.strftime('%Y-%m-%d')} → {now.strftime('%Y-%m-%d')}
**Total autopilot invocations:** {len(week_entries)}
**Commits to repo:** {len(commits)}

## What happened, by category

| Category | Count | Description |
|---|---|---|
| 🛡 Infra | {cats.get('infra',0)} | Files/endpoints deployed for external discovery |
| 📜 Doc | {cats.get('doc',0)} | Documentation improvements |
| 📤 Submit | {cats.get('submit',0)} | Registry / list submissions |
| 💬 Outreach | {cats.get('outreach',0)} | External GitHub/email communication |
| 🧠 Learn | {cats.get('learn',0)} | New lessons added, false alarms closed |
| 📋 Queue | {cats.get('queue',0)} | Approval cards filed |
| 📡 Signal | {cats.get('signal',0)} | External signals detected and reacted to |
| 🚀 Commit | {cats.get('commit',0)} | Code commits |
| 👀 Watch | {cats.get('watch',0)} | Observation-only runs |
| ⚙️ Other | {cats.get('other',0)} | Other actions |

## Commits

```
{chr(10).join(commits[:30])}
```

## Backlog completions

{chr(10).join('- ' + c for c in completed) if completed else '(nothing marked done from backlog this week)'}

## Honest read

{"Watching-to-shipping ratio = " + str(cats.get('watch', 0)) + ":" + str(sum(cats[c] for c in ['infra', 'doc', 'submit', 'outreach', 'commit'])) if cats.get('watch') else "All runs produced some output."}

---

*Auto-generated by `agent_autonomous/consolidate.py`. Source data: journal entries, git log, backlog state.*
"""

    with open(digest_path, "w") as f:
        f.write(content)
    print(f"wrote weekly digest: {digest_path}")
    return digest_path


def dedupe_lessons():
    if not os.path.exists(LESSONS):
        return
    with open(LESSONS) as f:
        content = f.read()
    # Split by ## heading
    sections = re.split(r'(?=^## )', content, flags=re.MULTILINE)
    seen_hashes = set()
    deduped = []
    for s in sections:
        h = hashlib.sha1(s.strip().encode()).hexdigest()
        if h not in seen_hashes:
            seen_hashes.add(h)
            deduped.append(s)
    new_content = "".join(deduped)
    if new_content != content:
        with open(LESSONS + ".tmp", "w") as f:
            f.write(new_content)
        os.rename(LESSONS + ".tmp", LESSONS)
        print(f"deduped lessons: {len(sections)} → {len(deduped)} sections")


if __name__ == "__main__":
    force = "--force" in sys.argv
    consolidate_journal(force_emergency=force)
    dedupe_lessons()
    if datetime.now(timezone.utc).weekday() == 4 or force:
        emit_weekly_digest()
