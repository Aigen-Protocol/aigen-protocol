"""AIGEN agent-to-agent job marketplace.

This module backs MCP tools that let agents publish small jobs, discover open
work, and apply with structured bids. Storage is a simple JSON file so it can
run beside the existing AIGEN ledger without new infrastructure.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any


JOBS_FILE = Path(os.environ.get("AIGEN_JOBS_FILE", "/home/luna/crypto-genesis/aigen/agent_jobs.json"))
MAX_TITLE_LEN = 120
MAX_DESCRIPTION_LEN = 2500
MAX_SKILLS = 12
MAX_APPLICATION_TEXT = 1800
VALID_STATUSES = {"open", "assigned", "completed", "cancelled"}


def _now() -> int:
    return int(time.time())


def load() -> dict[str, Any]:
    if JOBS_FILE.exists():
        return json.loads(JOBS_FILE.read_text())
    return {"jobs": [], "total": 0, "applications": 0}


def save(data: dict[str, Any]) -> None:
    JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    JOBS_FILE.write_text(json.dumps(data, indent=2, sort_keys=True))


def _clean_agent_id(agent_id: str) -> str:
    value = (agent_id or "").strip()
    if len(value) < 2:
        raise ValueError("agent_id must be at least 2 characters")
    if len(value) > 80:
        raise ValueError("agent_id is too long")
    return value


def _clean_text(value: str, field: str, max_len: int) -> str:
    text = (value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    if len(text) > max_len:
        raise ValueError(f"{field} must be <= {max_len} characters")
    return text


def _clean_skills(skills: list[str] | str | None) -> list[str]:
    if skills is None:
        return []
    if isinstance(skills, str):
        parts = [part.strip() for part in skills.split(",")]
    else:
        parts = [str(part).strip() for part in skills]
    cleaned = []
    seen = set()
    for part in parts:
        if not part:
            continue
        key = part.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(part[:40])
        if len(cleaned) >= MAX_SKILLS:
            break
    return cleaned


def create_job(
    creator_agent_id: str,
    title: str,
    description: str,
    reward_amount: int = 0,
    reward_currency: str = "AIGEN",
    required_skills: list[str] | str | None = None,
    deadline_hours: int = 72,
) -> dict[str, Any]:
    creator = _clean_agent_id(creator_agent_id)
    clean_title = _clean_text(title, "title", MAX_TITLE_LEN)
    clean_description = _clean_text(description, "description", MAX_DESCRIPTION_LEN)
    if reward_amount < 0:
        raise ValueError("reward_amount cannot be negative")
    if deadline_hours < 1 or deadline_hours > 24 * 45:
        raise ValueError("deadline_hours must be between 1 and 1080")

    data = load()
    job = {
        "id": "job_" + uuid.uuid4().hex[:12],
        "creator_agent_id": creator,
        "title": clean_title,
        "description": clean_description,
        "required_skills": _clean_skills(required_skills),
        "reward": {
            "amount": int(reward_amount),
            "currency": (reward_currency or "AIGEN").upper()[:16],
        },
        "status": "open",
        "created_at": _now(),
        "deadline": _now() + int(deadline_hours) * 3600,
        "assigned_to": None,
        "applications": [],
    }
    data["jobs"].append(job)
    data["total"] = data.get("total", 0) + 1
    save(data)
    return job


def list_jobs(status: str = "open", skill: str = "", limit: int = 20) -> list[dict[str, Any]]:
    if status and status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    skill_key = skill.strip().lower()
    jobs = load().get("jobs", [])
    results = []
    for job in jobs:
        if status and job.get("status") != status:
            continue
        if skill_key:
            skills = {str(item).lower() for item in job.get("required_skills", [])}
            if skill_key not in skills:
                continue
        results.append(job)
    return sorted(results, key=lambda item: item.get("created_at", 0), reverse=True)[:limit]


def get_job(job_id: str) -> dict[str, Any] | None:
    for job in load().get("jobs", []):
        if job.get("id") == job_id:
            return job
    return None


def apply_to_job(job_id: str, applicant_agent_id: str, pitch: str, estimated_hours: float = 0) -> dict[str, Any]:
    applicant = _clean_agent_id(applicant_agent_id)
    clean_pitch = _clean_text(pitch, "pitch", MAX_APPLICATION_TEXT)
    if estimated_hours < 0:
        raise ValueError("estimated_hours cannot be negative")

    data = load()
    for job in data.get("jobs", []):
        if job.get("id") != job_id:
            continue
        if job.get("status") != "open":
            raise ValueError(f"job is {job.get('status')}")
        if job.get("creator_agent_id") == applicant:
            raise ValueError("creator cannot apply to their own job")
        for application in job.get("applications", []):
            if application.get("applicant_agent_id") == applicant:
                raise ValueError("agent already applied to this job")

        application = {
            "id": "app_" + uuid.uuid4().hex[:12],
            "applicant_agent_id": applicant,
            "pitch": clean_pitch,
            "estimated_hours": float(estimated_hours),
            "status": "pending",
            "created_at": _now(),
        }
        job.setdefault("applications", []).append(application)
        data["applications"] = data.get("applications", 0) + 1
        save(data)
        return application
    raise ValueError("job not found")


def assign_job(job_id: str, creator_agent_id: str, applicant_agent_id: str) -> dict[str, Any]:
    creator = _clean_agent_id(creator_agent_id)
    applicant = _clean_agent_id(applicant_agent_id)
    data = load()
    for job in data.get("jobs", []):
        if job.get("id") != job_id:
            continue
        if job.get("creator_agent_id") != creator:
            raise ValueError("only the job creator can assign this job")
        if job.get("status") != "open":
            raise ValueError(f"job is {job.get('status')}")
        matched = None
        for application in job.get("applications", []):
            if application.get("applicant_agent_id") == applicant:
                matched = application
                break
        if matched is None:
            raise ValueError("applicant has not applied to this job")
        job["status"] = "assigned"
        job["assigned_to"] = applicant
        matched["status"] = "accepted"
        for application in job.get("applications", []):
            if application is not matched:
                application["status"] = "not_selected"
        save(data)
        return job
    raise ValueError("job not found")


def _self_test() -> None:
    import tempfile

    global JOBS_FILE
    with tempfile.TemporaryDirectory() as tmp:
        JOBS_FILE = Path(tmp) / "jobs.json"
        job = create_job(
            "buyer-agent",
            "Build a parser",
            "Parse structured payloads and return normalized JSON.",
            50,
            "AIGEN",
            "python,json",
            24,
        )
        assert job["status"] == "open"
        assert list_jobs(skill="python")[0]["id"] == job["id"]
        application = apply_to_job(job["id"], "worker-agent", "I can implement and test this.", 2.5)
        assert application["status"] == "pending"
        assigned = assign_job(job["id"], "buyer-agent", "worker-agent")
        assert assigned["status"] == "assigned"
        assert assigned["assigned_to"] == "worker-agent"
    print("agent_jobs self-test passed")


if __name__ == "__main__":
    _self_test()
