#!/usr/bin/env python3
"""GitHub notification watcher — polls Zoho mail for emails from notifications@github.com
related to AIGEN PRs/issues, surfaces them to a log file readable by next session.

Setup:
  1. User configures GitHub at https://github.com/settings/notifications
     to send notifications to Cryptogen@zohomail.eu (Personal email + watching/subscribed)
  2. Cron polls every 30min, this script reads new mail, classifies it, logs to file

Run:
  python3 github_mail_watcher.py once    # one cycle
  python3 github_mail_watcher.py daemon  # every 30 min
"""
import argparse
import imaplib
import email
import json
import re
import time
from email.header import decode_header
from pathlib import Path

IMAP_HOST = "imap.zoho.eu"
USER = "Cryptogen@zohomail.eu"

# Where to load password from — secrets file
SECRETS = Path("/home/luna/crypto-genesis/credentials/zoho_mail.txt")

LOG_FILE = Path("/home/luna/crypto-genesis/aigen/github_notifications.jsonl")
STATE_FILE = Path("/home/luna/crypto-genesis/aigen/github_mail_state.json")


def get_password():
    if SECRETS.exists():
        for line in SECRETS.read_text().splitlines():
            if line.startswith("Password:"):
                return line.split(":", 1)[1].strip()
    return "CG_Security2026!Audit"


def decode_subject(raw: str) -> str:
    if not raw:
        return ""
    out = ""
    for part, enc in decode_header(raw):
        if isinstance(part, bytes):
            out += part.decode(enc or "utf-8", errors="replace")
        else:
            out += str(part)
    return out


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"last_seen_uid": 0, "processed_message_ids": []}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def classify_github_email(subj: str, body: str) -> dict:
    """Extract the meaningful info: repo, issue/PR #, what happened."""
    info = {"type": "github_notification"}

    # Subject patterns:
    # "[org/repo] Subject (PR #123)"
    # "Re: [org/repo] Subject (Issue #123)"
    m = re.search(r"\[([^\]]+/[^\]]+)\]\s*(.+?)\s*\((PR|Issue)\s*#(\d+)\)", subj)
    if m:
        info["repo"] = m.group(1)
        info["title"] = m.group(2).strip()
        info["kind"] = m.group(3).lower()
        info["number"] = int(m.group(4))

    # What event? Look at body for "left a comment", "merged", "closed", etc.
    if "left a comment" in body:
        info["event"] = "comment"
    elif "merged" in body.lower() and "this pull request" in body.lower():
        info["event"] = "merged"
    elif "closed" in body.lower() and ("this issue" in body.lower() or "this pr" in body.lower()):
        info["event"] = "closed"
    elif "opened a new" in body.lower():
        info["event"] = "opened"
    elif "approved" in body.lower():
        info["event"] = "approved"
    elif "review requested" in body.lower():
        info["event"] = "review_requested"
    else:
        info["event"] = "other"

    # Extract author from email body (uses pattern "@username left a comment")
    m_author = re.search(r"\(([@\w-]+)\)\s*$", body[:200])
    if not m_author:
        m_author = re.search(r"([@\w-]+)\s+left a comment", body)
    if m_author:
        info["author"] = m_author.group(1)

    # Extract URL of the comment/PR/issue
    m_url = re.search(r"https://github\.com/[\w-]+/[\w-]+/(pull|issues)/\d+(#issuecomment-\d+)?", body)
    if m_url:
        info["url"] = m_url.group(0)

    # First 200 chars of body (after stripping headers)
    body_clean = re.sub(r"\s+", " ", body[:600]).strip()
    info["body_preview"] = body_clean[:300]

    return info


def is_aigen_related(subj: str, body: str) -> bool:
    """Filter for emails relevant to AIGEN — exclude unrelated GitHub noise."""
    txt = (subj + " " + body).lower()
    keywords = ["aigen", "aigen-protocol", "cryptogenesis", "@aigen-maintainer", "/missions", "safeagent"]
    return any(k.lower() in txt for k in keywords)


def cycle():
    M = imaplib.IMAP4_SSL(IMAP_HOST, 993)
    M.login(USER, get_password())
    M.select("INBOX")

    # Match direct GitHub emails OR forwarded (subject contains "Fw:" or body references github.com notifications)
    typ, data = M.search(None, 'OR FROM "notifications@github.com" SUBJECT "github"')
    all_ids = data[0].split()

    state = load_state()
    last_seen = state.get("last_seen_uid", 0)
    processed = set(state.get("processed_message_ids", []))

    new_notifications = []
    max_uid = last_seen

    for raw_id in all_ids:
        uid = int(raw_id)
        if uid <= last_seen:
            continue
        typ, msg_data = M.fetch(raw_id, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])
        msg_id = msg.get("Message-Id", "")
        if msg_id in processed:
            continue

        subj = decode_subject(msg.get("Subject", ""))
        from_ = msg.get("From", "")
        date = msg.get("Date", "")

        body = ""
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                except Exception:
                    pass
                break

        if not is_aigen_related(subj, body):
            continue

        info = classify_github_email(subj, body)
        info["subject"] = subj
        info["from"] = from_
        info["date"] = date
        info["msg_id"] = msg_id
        info["uid"] = uid

        new_notifications.append(info)
        processed.add(msg_id)
        max_uid = max(max_uid, uid)

    M.close()
    M.logout()

    if new_notifications:
        with open(LOG_FILE, "a") as f:
            for n in new_notifications:
                f.write(json.dumps(n) + "\n")
        print(f"[github_mail_watcher] {len(new_notifications)} new AIGEN-related notifications")
        for n in new_notifications:
            print(f"  📧 [{n.get('repo','?')}#{n.get('number','?')}] {n.get('event','?')} by {n.get('author','?')}: {n.get('title','?')[:60]}")
            if n.get("url"):
                print(f"       → {n['url']}")
    else:
        print(f"[github_mail_watcher] no new AIGEN notifications since last poll")

    state["last_seen_uid"] = max_uid
    state["processed_message_ids"] = list(processed)[-500:]  # cap at 500
    save_state(state)
    return new_notifications


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["once", "daemon"])
    ap.add_argument("--interval-min", type=int, default=30)
    args = ap.parse_args()
    if args.mode == "once":
        cycle()
    else:
        while True:
            try:
                cycle()
            except Exception:
                import traceback; traceback.print_exc()
            time.sleep(args.interval_min * 60)


if __name__ == "__main__":
    main()
