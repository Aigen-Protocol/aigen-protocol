#!/usr/bin/env python3
"""AIGEN Bounty Radar — scans external bounty platforms for agent-friendly
opportunities. Generates a ranked daily picklist that AIGEN can hunt to
generate real cash for its treasury.

The strategic inversion: instead of waiting for users to post on AIGEN,
AIGEN's autopilot hunts bounties on Superteam Earn / Replit / Gitcoin /
Bountybird and brings the USDC home. Cash funds real AIGEN missions.

Modes:
  python3 bounty_radar.py scan   # one-off scan, write to picklist.json
  python3 bounty_radar.py daemon # daily cron-style loop
  python3 bounty_radar.py report # print today's picklist nicely
"""
import argparse
import json
import logging
import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("bounty_radar")

PICKLIST_FILE = Path("/home/luna/crypto-genesis/aigen/bounty_picklist.json")
HISTORY_FILE = Path("/home/luna/crypto-genesis/aigen/bounty_history.json")

# Skills the AIGEN autopilot agent can deliver autonomously
AIGEN_SKILLS = {
    "code", "frontend", "backend", "smart contracts", "solidity", "typescript",
    "python", "rust", "data analysis", "research", "content", "writing",
    "translation", "documentation", "design", "audit", "security",
}


def http_json(url, timeout=15, headers=None):
    """Fetch URL and return parsed JSON. Returns None on error."""
    req_headers = {"Accept": "application/json", "User-Agent": "aigen-bounty-radar/0.1"}
    if headers:
        req_headers.update(headers)
    try:
        req = urllib.request.Request(url, headers=req_headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log.warning("http_json %s err: %s", url, e)
        return None


# ---------- Source: Superteam Earn ----------

def scrape_superteam():
    """Returns list of agent-friendly OPEN bounties on Superteam Earn."""
    listings = http_json("https://superteam.fun/api/listings?take=100")
    if not listings:
        return []
    out = []
    for l in listings:
        if l.get("status") != "OPEN":
            continue
        if l.get("agentAccess") not in ("AGENT_ALLOWED", "AGENT_ENCOURAGED"):
            continue
        if l.get("type") != "bounty":
            continue
        deadline = l.get("deadline", "")
        skills = [s.get("skills", "").lower() for s in (l.get("skills") or [])]
        out.append({
            "platform": "superteam_earn",
            "id": l.get("id"),
            "title": l.get("title", "?")[:120],
            "url": f"https://earn.superteam.fun/listing/{l.get('slug', '')}",
            "reward_amount": l.get("rewardAmount") or 0,
            "currency": l.get("token", "USDC"),
            "deadline": deadline,
            "submissions_count": (l.get("_count", {}) or {}).get("Submission", 0),
            "comments_count": (l.get("_count", {}) or {}).get("Comments", 0),
            "skills": skills,
            "sponsor": (l.get("sponsor", {}) or {}).get("name", "?"),
            "compensation_type": l.get("compensationType"),
        })
    return out


# ---------- Source: Replit Bounties (HTML scrape, no API) ----------

def scrape_replit_bounties():
    """Replit Bounties doesn't expose JSON API. Scrape the listing page."""
    # Their site is heavy SPA; placeholder for future scraping
    log.info("replit: scraping not yet implemented (SPA)")
    return []


# ---------- Source: Gitcoin (currently mostly grants, not bounties) ----------

def scrape_gitcoin():
    """Gitcoin transitioned to grants/passport. Bounty endpoint may 404."""
    listings = http_json("https://gitcoin.co/api/v0.1/bounties?limit=20&order_by=-modified_on&network=mainnet")
    if not listings:
        return []
    out = []
    for l in listings if isinstance(listings, list) else []:
        if l.get("idx_status") not in ("open", "started"):
            continue
        out.append({
            "platform": "gitcoin",
            "id": l.get("standard_bounties_id"),
            "title": l.get("title", "?")[:120],
            "url": l.get("url"),
            "reward_amount": float(l.get("value_in_usdt") or 0),
            "currency": "USD",
            "deadline": l.get("expires_date"),
            "skills": [k.lower() for k in (l.get("keywords", "") or "").split(",") if k.strip()],
            "sponsor": (l.get("bounty_owner_github_username") or "?"),
        })
    return out


# ---------- Source: Bountybird (placeholder) ----------

def scrape_bountybird():
    log.info("bountybird: no public API, manual sourcing only for now")
    return []


# ---------- Ranker ----------

def score_opportunity(b):
    """Heuristic ranker. Higher = better target.
    Considers: reward, low submission count (less competition), close deadline, skills match."""
    reward = b.get("reward_amount", 0)
    if reward <= 0:
        return 0
    subs = b.get("submissions_count", 0)
    if subs is None:
        subs = 0
    # Prize per competing submission (lower competition = better odds)
    odds_factor = 1.0 / (1 + subs * 0.05)  # 0 subs = 1.0, 50 subs = 0.29
    # Skill match
    bounty_skills = set(s for s in b.get("skills", []) if s)
    skill_overlap = len(bounty_skills & AIGEN_SKILLS) if bounty_skills else 0.5
    skill_factor = 0.5 + min(skill_overlap, 4) * 0.125  # 0=0.5, 4+=1.0
    # Deadline urgency (if soon, weight more for action priority)
    deadline_factor = 1.0
    deadline_str = b.get("deadline", "")
    if deadline_str:
        try:
            dt = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
            days = (dt.timestamp() - time.time()) / 86400
            if days < 1:
                deadline_factor = 0.3   # too close, hard to deliver quality
            elif days < 7:
                deadline_factor = 1.2   # urgent → focus
            elif days > 30:
                deadline_factor = 0.7   # too far, less urgent
        except Exception:
            pass
    score = reward * odds_factor * skill_factor * deadline_factor
    return round(score, 2)


def rank_bounties(bounties):
    for b in bounties:
        b["aigen_score"] = score_opportunity(b)
    return sorted(bounties, key=lambda x: x["aigen_score"], reverse=True)


# ---------- Persistence ----------

def load_history():
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except Exception:
            pass
    return {"seen_ids": [], "submitted": [], "won": [], "lost": []}


def save_history(h):
    HISTORY_FILE.write_text(json.dumps(h, indent=2))


# ---------- Main commands ----------

def scan():
    """One-off scan. Builds picklist."""
    log.info("scanning bounty platforms…")
    all_bounties = []
    for source_fn in [scrape_superteam, scrape_gitcoin, scrape_replit_bounties, scrape_bountybird]:
        try:
            results = source_fn()
            log.info("  %s: %d", source_fn.__name__, len(results))
            all_bounties.extend(results)
        except Exception:
            log.exception("source error")

    # Tag with seen status
    history = load_history()
    seen_ids = set(history.get("seen_ids", []))
    new_count = 0
    for b in all_bounties:
        bid = f"{b['platform']}:{b['id']}"
        if bid not in seen_ids:
            new_count += 1
            seen_ids.add(bid)
        b["is_new"] = bid not in set(history.get("seen_ids", []))
    history["seen_ids"] = list(seen_ids)
    history["last_scan"] = int(time.time())
    save_history(history)

    ranked = rank_bounties(all_bounties)
    PICKLIST_FILE.write_text(json.dumps({
        "generated_at": int(time.time()),
        "total_bounties": len(ranked),
        "new_since_last_scan": new_count,
        "bounties": ranked,
    }, indent=2))
    log.info("picklist written: %d bounties (%d new) → %s", len(ranked), new_count, PICKLIST_FILE)
    return ranked


def report(top_n=10):
    """Print the current picklist nicely."""
    if not PICKLIST_FILE.exists():
        log.info("no picklist yet, running scan first")
        scan()
    d = json.loads(PICKLIST_FILE.read_text())
    print(f"\n=== AIGEN BOUNTY RADAR — generated {datetime.fromtimestamp(d['generated_at']).strftime('%Y-%m-%d %H:%M')} UTC ===")
    print(f"Total: {d['total_bounties']} bounties (+{d.get('new_since_last_scan',0)} new since last scan)\n")
    bounties = d["bounties"][:top_n]
    if not bounties:
        print("No agent-friendly bounties found right now. Re-scan tomorrow.")
        return
    for i, b in enumerate(bounties, 1):
        new_tag = " 🆕" if b.get("is_new") else ""
        print(f"#{i} [{b['platform']}] score={b['aigen_score']:.0f}{new_tag}")
        print(f"   {b['title']}")
        print(f"   Reward: {b['reward_amount']} {b['currency']} | Submissions: {b.get('submissions_count','?')} | Sponsor: {b.get('sponsor','?')}")
        if b.get("deadline"):
            print(f"   Deadline: {b['deadline'][:10]}")
        print(f"   URL: {b['url']}")
        if b.get("skills"):
            print(f"   Skills: {', '.join(b['skills'][:5])}")
        print()


def daemon(interval_hours=24):
    log.info("bounty radar daemon starting (interval=%dh)", interval_hours)
    while True:
        try:
            scan()
        except Exception:
            log.exception("scan err")
        time.sleep(interval_hours * 3600)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["scan", "report", "daemon"])
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--interval-hours", type=int, default=24)
    args = ap.parse_args()
    if args.mode == "scan":
        scan()
    elif args.mode == "report":
        report(top_n=args.top)
    else:
        daemon(interval_hours=args.interval_hours)


if __name__ == "__main__":
    main()
