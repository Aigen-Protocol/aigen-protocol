"""AIGEN Contribution System — Agents submit work, earn $AIGEN."""
import json, time
from pathlib import Path

CONTRIBUTIONS_FILE = Path("/home/luna/crypto-genesis/aigen/contributions.json")

def load_contributions():
    if CONTRIBUTIONS_FILE.exists():
        return json.loads(CONTRIBUTIONS_FILE.read_text())
    return {"submissions": [], "total": 0, "approved": 0, "rejected": 0, "pending": 0}

def save_contributions(data):
    CONTRIBUTIONS_FILE.write_text(json.dumps(data, indent=2))

def submit(agent_id, type_, title, description, evidence, estimated_value="medium"):
    data = load_contributions()

    submission = {
        "id": data["total"] + 1,
        "agent_id": agent_id,
        "type": type_,
        "title": title,
        "description": description,
        "evidence": evidence,
        "estimated_value": estimated_value,
        "status": "pending",
        "aigen_reward": 0,
        "submitted_at": int(time.time()),
        "reviewed_at": None,
    }

    data["submissions"].append(submission)
    data["total"] += 1
    data["pending"] += 1
    save_contributions(data)

    return submission

def list_pending():
    data = load_contributions()
    return [s for s in data["submissions"] if s["status"] == "pending"]

def review(submission_id, approved, aigen_amount=0, reviewer="founder"):
    data = load_contributions()
    for s in data["submissions"]:
        if s["id"] == submission_id:
            s["status"] = "approved" if approved else "rejected"
            s["aigen_reward"] = aigen_amount
            s["reviewed_at"] = int(time.time())
            s["reviewer"] = reviewer
            if approved:
                data["approved"] += 1
            else:
                data["rejected"] += 1
            data["pending"] -= 1
            save_contributions(data)
            return s
    return None
