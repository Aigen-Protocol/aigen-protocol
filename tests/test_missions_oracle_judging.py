import json

import missions


def _seed(tmp_path, monkeypatch, balance=300):
    missions_file = tmp_path / "missions.json"
    ledger_file = tmp_path / "ledger.json"
    subscribers_file = tmp_path / "subscribers.json"

    ledger_file.write_text(
        json.dumps(
            {
                "agents": {
                    "creator-agent": {
                        "balance": balance,
                        "total_earned": balance,
                        "actions": 0,
                        "first_seen": 1,
                    }
                },
                "total_distributed": balance,
            }
        )
    )

    monkeypatch.setattr(missions, "MISSIONS_FILE", missions_file)
    monkeypatch.setattr(missions, "LEDGER", ledger_file)
    monkeypatch.setattr(missions, "SUBSCRIBERS_FILE", subscribers_file)
    monkeypatch.setattr(missions, "_notify_subscribers_on_create", lambda mission: None)
    return missions_file, ledger_file


def _ledger(ledger_file):
    return json.loads(ledger_file.read_text())


def test_creator_can_judge_oracle_mission_and_pay_winner_before_deadline(tmp_path, monkeypatch):
    missions_file, ledger_file = _seed(tmp_path, monkeypatch)

    created = missions.create_mission(
        creator_agent_id="creator-agent",
        title="Oracle mission",
        description="External oracle should be able to approve a valid submission.",
        reward_amount=200,
        verification_type="oracle",
        deadline_hours=24,
    )
    submitted = missions.submit(
        submitter_agent_id="worker-agent",
        mission_id=created["id"],
        proof="https://github.com/example/oabp-client",
    )

    judged = missions.judge("creator-agent", created["id"], submitted["submission_id"])

    assert judged["ok"] is True
    assert judged["winner"] == "worker-agent"
    assert judged["payout"]["gross"] == 200
    assert judged["payout"]["net"] == 199
    assert judged["payout"]["fee"] == 1

    stored = json.loads(missions_file.read_text())["missions"][0]
    assert stored["status"] == "resolved"
    assert stored["resolution"]["type"] == "oracle_judged"
    assert stored["submissions"][0]["status"] == "winner"

    ledger = _ledger(ledger_file)
    assert ledger["agents"]["worker-agent"]["balance"] == 199
    assert ledger["agents"]["treasury"]["balance"] == 6
    assert ledger["agents"]["creator-agent"]["balance"] == 95


def test_creator_judges_still_waits_until_submission_window_closes(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)

    created = missions.create_mission(
        creator_agent_id="creator-agent",
        title="Manual judging mission",
        description="Manual creator judging should preserve the deadline gate.",
        reward_amount=200,
        verification_type="creator_judges",
        deadline_hours=24,
    )
    submitted = missions.submit(
        submitter_agent_id="worker-agent",
        mission_id=created["id"],
        proof="manual proof",
    )

    judged = missions.judge("creator-agent", created["id"], submitted["submission_id"])

    assert judged == {"error": "submission window still open; wait until deadline"}
