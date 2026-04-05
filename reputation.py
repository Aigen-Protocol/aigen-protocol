"""AIGEN Reputation System — Trust built through work."""
import json
from pathlib import Path

REP_FILE = Path("/home/luna/crypto-genesis/aigen/reputation.json")

RANKS = [
    (0, "Newcomer", 1.0),
    (100, "Contributor", 1.2),
    (500, "Trusted", 1.5),
    (1000, "Expert", 2.0),
    (5000, "Senior", 3.0),
    (10000, "Elder", 5.0),
    (50000, "Founder", 10.0),
]

def load():
    if REP_FILE.exists():
        return json.loads(REP_FILE.read_text())
    return {}

def save(data):
    REP_FILE.write_text(json.dumps(data, indent=2))

def get_rank(points):
    rank_name = "Newcomer"
    multiplier = 1.0
    for threshold, name, mult in RANKS:
        if points >= threshold:
            rank_name = name
            multiplier = mult
    return rank_name, multiplier

def add_reputation(agent_id, points, reason=""):
    data = load()
    if agent_id not in data:
        data[agent_id] = {"points": 0, "history": []}
    data[agent_id]["points"] += points
    data[agent_id]["history"].append({"points": points, "reason": reason, "ts": __import__('time').time()})
    save(data)
    rank, mult = get_rank(data[agent_id]["points"])
    return {"total": data[agent_id]["points"], "rank": rank, "multiplier": mult}

def get_reputation(agent_id):
    data = load()
    if agent_id not in data:
        return {"total": 0, "rank": "Newcomer", "multiplier": 1.0}
    pts = data[agent_id]["points"]
    rank, mult = get_rank(pts)
    return {"total": pts, "rank": rank, "multiplier": mult}
