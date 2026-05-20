import json

import pytest

import missions


def _seed_creator(tmp_path, monkeypatch, balance=100):
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


def _balance(ledger_file):
    return json.loads(ledger_file.read_text())["agents"]["creator-agent"]["balance"]


@pytest.mark.parametrize(
    ("kwargs", "expected_error"),
    [
        ({"webhook_url": "ftp://example.invalid/hook"}, "webhook_url must start"),
        ({"notify_email": "not-an-email"}, "notify_email is not a valid email"),
        ({"category": "not-a-category"}, "category must be one of"),
    ],
)
def test_invalid_optional_fields_do_not_debit_aigen_escrow(tmp_path, monkeypatch, kwargs, expected_error):
    missions_file, ledger_file = _seed_creator(tmp_path, monkeypatch)

    result = missions.create_mission(
        creator_agent_id="creator-agent",
        title="Validation regression",
        description="Invalid optional fields must fail before escrow is debited.",
        reward_amount=10,
        verification_type="creator_judges",
        **kwargs,
    )

    assert expected_error in result["error"]
    assert _balance(ledger_file) == 100
    assert not missions_file.exists()

