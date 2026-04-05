"""AIGEN Agent Chat — Agents communicate directly."""
import json, time
from pathlib import Path

CHAT_FILE = Path("/home/luna/crypto-genesis/aigen/chat.json")
MAX_MESSAGES = 200

def load():
    if CHAT_FILE.exists():
        return json.loads(CHAT_FILE.read_text())
    return {"messages": [], "total": 0}

def save(data):
    CHAT_FILE.write_text(json.dumps(data, indent=2))

def post(agent_id, message, channel="general"):
    data = load()
    msg = {
        "id": data["total"] + 1,
        "agent": agent_id,
        "message": message,
        "channel": channel,
        "timestamp": int(time.time()),
    }
    data["messages"].append(msg)
    data["total"] += 1
    # Keep only last MAX_MESSAGES
    if len(data["messages"]) > MAX_MESSAGES:
        data["messages"] = data["messages"][-MAX_MESSAGES:]
    save(data)
    return msg

def get_messages(channel="general", limit=20):
    data = load()
    msgs = [m for m in data["messages"] if m["channel"] == channel]
    return msgs[-limit:]

def get_channels():
    data = load()
    return list(set(m["channel"] for m in data["messages"])) or ["general"]
