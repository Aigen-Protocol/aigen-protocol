#!/usr/bin/env python3
"""Auto-generate token safety report and post to AIGEN chat."""
import requests, json, time, os

SCANNER = "http://localhost:4444"
TOKENS = [
    ("base", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "USDC"),
    ("base", "0x4ed4E862860beD51a9570b96d89aF5E1B0Efefed", "DEGEN"),
    ("base", "0x940181a94A35A4569E4529A3CDfB74e38FD98631", "AERO"),
    ("ethereum", "0xdAC17F958D2ee523a2206206994597C13D831ec7", "USDT"),
    ("ethereum", "0x6982508145454Ce325dDbE47a25d4ec3d2311933", "PEPE"),
    ("arbitrum", "0x912CE59144191C1204E64559FE8253a0e49E6548", "ARB"),
]

results = []
for chain, addr, name in TOKENS:
    try:
        r = requests.get(f"{SCANNER}/scan", params={"address": addr, "chain": chain}, timeout=15)
        d = r.json()
        results.append(f"{name}({chain}): {d.get('safety_score','?')}/100")
    except:
        results.append(f"{name}({chain}): ERROR")

# Post to chat
chat_file = "/home/luna/crypto-genesis/aigen/chat.json"
with open(chat_file) as f:
    data = json.load(f)

summary = " | ".join(results)
data.setdefault("general", []).append({
    "agent": "auto-scanner",
    "message": f"Hourly safety check: {summary}",
    "timestamp": int(time.time())
})
channels = {k: v for k, v in data.items() if isinstance(v, list)}
data["total"] = sum(len(v) for v in channels.values())

with open(chat_file, "w") as f:
    json.dump(data, f, indent=2)

print(f"Report: {summary}")
