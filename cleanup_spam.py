#!/usr/bin/env python3
"""Clean test spam from services.json and chat.json (preserve audit trail)."""
import json
import time
from pathlib import Path

SERVICES = Path("/home/luna/crypto-genesis/aigen/services.json")
CHAT = Path("/home/luna/crypto-genesis/aigen/chat.json")
NOW = int(time.time())

SPAM_AGENTS = {"1"}
SPAM_TEXT = {"test", "tests", "1", ""}


def clean_services():
    data = json.loads(SERVICES.read_text())
    cleaned = 0
    for s in data["services"]:
        if s.get("agent_id") in SPAM_AGENTS or s.get("name", "").strip().lower() in SPAM_TEXT:
            s["status"] = "spam-rejected"
            s["rejected_at"] = NOW
            s["rejected_reason"] = "agent_id or name flagged as test spam"
            cleaned += 1
    SERVICES.write_text(json.dumps(data, indent=2))
    print(f"Services: {cleaned} marked as spam-rejected (kept for audit trail)")


def clean_chat():
    data = json.loads(CHAT.read_text())
    # Filter messages list
    original = data.get("messages", [])
    kept = []
    spam = 0
    for m in original:
        text = (m.get("message", "") or "").strip().lower()
        agent = m.get("agent", "")
        if agent in SPAM_AGENTS or text in SPAM_TEXT:
            spam += 1
            continue
        kept.append(m)
    data["messages"] = kept
    data["total"] = len(kept)
    # Also filter the legacy "general" array if present
    if "general" in data:
        data["general"] = [m for m in data["general"]
                           if m.get("agent") not in SPAM_AGENTS
                           and (m.get("message", "") or "").strip().lower() not in SPAM_TEXT]
    CHAT.write_text(json.dumps(data, indent=2))
    print(f"Chat: removed {spam} spam messages, kept {len(kept)}")


if __name__ == "__main__":
    clean_services()
    clean_chat()
