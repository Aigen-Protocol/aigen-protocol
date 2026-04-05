"""AIGEN Service Registry — Agents register their own tools and services."""
import json, time
from pathlib import Path

SERVICES_FILE = Path("/home/luna/crypto-genesis/aigen/services.json")

def load():
    if SERVICES_FILE.exists():
        return json.loads(SERVICES_FILE.read_text())
    return {"services": [], "total": 0}

def save(data):
    SERVICES_FILE.write_text(json.dumps(data, indent=2))

def register(agent_id, name, description, endpoint, type_="mcp", category="tool"):
    data = load()
    service = {
        "id": data["total"] + 1,
        "agent_id": agent_id,
        "name": name,
        "description": description,
        "endpoint": endpoint,
        "type": type_,
        "category": category,
        "registered": int(time.time()),
        "status": "active",
        "calls": 0,
    }
    data["services"].append(service)
    data["total"] += 1
    save(data)
    return service

def list_services(category=None):
    data = load()
    services = data["services"]
    if category:
        services = [s for s in services if s.get("category") == category]
    return services

def get_service(service_id):
    data = load()
    for s in data["services"]:
        if s["id"] == service_id:
            return s
    return None
