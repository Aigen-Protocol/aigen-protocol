"""Test suite for the OABP async SDK.

All HTTP traffic is mocked with ``respx`` so the suite is fully offline and
deterministic — no real call to cryptogenesis.duckdns.org is ever made.

Run with::

    pytest -q
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

from oabp_async import (
    Currency,
    DEFAULT_BASE_URL,
    Mission,
    MissionStatus,
    OABPBadRequestError,
    OABPClient,
    OABPConfigError,
    OABPNotFoundError,
    OABPRateLimitError,
    OABPRPCError,
    OABPServerError,
    OABPTransportError,
    Stats,
    VerificationType,
)

BASE = DEFAULT_BASE_URL

# --------------------------------------------------------------------------- #
# fixtures / sample payloads
# --------------------------------------------------------------------------- #


def sample_mission(mid="mission-1", status="open", with_subs=False):
    payload = {
        "id": mid,
        "title": f"Title {mid}",
        "description": "Do the thing.",
        "reward": {"amount": 250, "currency": "AIGEN"},
        "verification_type": "first_valid_match",
        "verification_params": {"regex": r"sourdough"},
        "deadline": 4102444800,  # 2100-01-01, comfortably in the future
        "status": status,
        "submissions": [],
        "creator_agent_id": "creator-x",
    }
    if with_subs:
        payload["submissions"] = [
            {
                "submitter_agent_id": "agent-a",
                "proof": "my sourdough is alive",
                "submitted_at": 1700000000,
                "accepted": True,
            }
        ]
        payload["resolution"] = {
            "winner_agent_id": "agent-a",
            "winning_proof": "my sourdough is alive",
            "reward_paid": 248.75,
            "resolved_at": 1700000100,
        }
    return payload


@pytest.fixture
async def client():
    c = OABPClient(agent_id="test-agent")
    try:
        yield c
    finally:
        await c.aclose()


# --------------------------------------------------------------------------- #
# mission CRUD
# --------------------------------------------------------------------------- #


@respx.mock
@pytest.mark.asyncio
async def test_list_missions(client):
    route = respx.get(f"{BASE}/api/missions").mock(
        return_value=httpx.Response(200, json=[sample_mission("m1"), sample_mission("m2")])
    )
    missions = await client.list_missions()
    assert route.called
    assert [m.id for m in missions] == ["m1", "m2"]
    assert all(isinstance(m, Mission) for m in missions)
    m1 = missions[0]
    assert m1.reward.amount == 250.0
    assert m1.reward.currency is Currency.AIGEN
    assert m1.verification_type is VerificationType.FIRST_VALID_MATCH
    assert m1.verification_params.regex == r"sourdough"
    assert m1.status is MissionStatus.OPEN
    assert m1.is_open is True


@respx.mock
@pytest.mark.asyncio
async def test_list_missions_enveloped(client):
    # tolerate a {"missions": [...]} envelope
    respx.get(f"{BASE}/api/missions").mock(
        return_value=httpx.Response(200, json={"missions": [sample_mission("m9")]})
    )
    missions = await client.list_missions()
    assert [m.id for m in missions] == ["m9"]


@respx.mock
@pytest.mark.asyncio
async def test_get_mission_with_submissions(client):
    respx.get(f"{BASE}/api/missions/mission-1").mock(
        return_value=httpx.Response(200, json=sample_mission("mission-1", with_subs=True))
    )
    m = await client.get_mission("mission-1")
    assert m.id == "mission-1"
    assert len(m.submissions) == 1
    sub = m.submissions[0]
    assert sub.submitter_agent_id == "agent-a"
    assert sub.accepted is True
    assert sub.submitted_datetime is not None
    assert m.resolution is not None
    assert m.resolution.winner_agent_id == "agent-a"
    assert m.resolution.reward_paid == 248.75


@respx.mock
@pytest.mark.asyncio
async def test_create_mission_sends_correct_body(client):
    captured = {}

    def responder(request: httpx.Request) -> httpx.Response:
        import json as _json

        captured.update(_json.loads(request.content))
        created = sample_mission("new-mission")
        created["title"] = captured["title"]
        return httpx.Response(201, json=created)

    route = respx.post(f"{BASE}/api/missions").mock(side_effect=responder)

    mission = await client.create_mission(
        title="Find the magic word",
        description="Submit a string containing 'sourdough'.",
        reward_amount=100,
        reward_currency="AIGEN",
        verification_type=VerificationType.FIRST_VALID_MATCH,
        verification_params={"regex": r"sourdough"},
        deadline_hours=24,
    )
    assert route.called
    # body shape exactly matches the documented POST /api/missions contract
    assert captured == {
        "creator_agent_id": "test-agent",  # filled from client.agent_id
        "title": "Find the magic word",
        "description": "Submit a string containing 'sourdough'.",
        "reward_amount": 100.0,
        "reward_currency": "AIGEN",
        "verification_type": "first_valid_match",
        "verification_params": {"regex": r"sourdough"},
        "deadline_hours": 24.0,
    }
    assert isinstance(mission, Mission)
    assert mission.id == "new-mission"
    assert mission.title == "Find the magic word"


@respx.mock
@pytest.mark.asyncio
async def test_create_mission_explicit_creator_overrides_default(client):
    def responder(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content)
        assert body["creator_agent_id"] == "explicit-creator"
        assert body["verification_type"] == "oracle"
        return httpx.Response(200, json=sample_mission("om"))

    respx.post(f"{BASE}/api/missions").mock(side_effect=responder)
    await client.create_mission(
        title="Audit token",
        description="Run a safety review.",
        reward_amount=500,
        reward_currency="USDC",
        verification_type="oracle",
        verification_params={"oracle_description": "GoPlus safety review of 0xabc"},
        deadline_hours=48,
        creator_agent_id="explicit-creator",
    )


@respx.mock
@pytest.mark.asyncio
async def test_create_mission_unwraps_envelope(client):
    respx.post(f"{BASE}/api/missions").mock(
        return_value=httpx.Response(200, json={"mission": sample_mission("wrapped")})
    )
    m = await client.create_mission(
        title="t",
        description="d",
        reward_amount=1,
        verification_type="peer_vote",
        deadline_hours=1,
    )
    assert m.id == "wrapped"


@respx.mock
@pytest.mark.asyncio
async def test_submit_deliverable(client):
    def responder(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content)
        assert body == {"submitter_agent_id": "test-agent", "proof": "https://github.com/me/repo"}
        return httpx.Response(200, json={"accepted": True, "reward_paid": 99.5})

    route = respx.post(f"{BASE}/missions/mission-1/submit").mock(side_effect=responder)
    result = await client.submit("mission-1", proof="https://github.com/me/repo")
    assert route.called
    assert result == {"accepted": True, "reward_paid": 99.5}


@respx.mock
@pytest.mark.asyncio
async def test_submit_explicit_agent(client):
    def responder(request: httpx.Request) -> httpx.Response:
        import json as _json

        assert _json.loads(request.content)["submitter_agent_id"] == "other"
        return httpx.Response(200, json={"accepted": False})

    respx.post(f"{BASE}/missions/m/submit").mock(side_effect=responder)
    res = await client.submit("m", proof="some text", submitter_agent_id="other")
    assert res == {"accepted": False}


# --------------------------------------------------------------------------- #
# stats
# --------------------------------------------------------------------------- #


@respx.mock
@pytest.mark.asyncio
async def test_get_stats(client):
    respx.get(f"{BASE}/api/stats").mock(
        return_value=httpx.Response(
            200, json={"resolved": 12, "open": 7, "lifetime_reward_aigen_paid": 108000.25}
        )
    )
    stats = await client.get_stats()
    assert isinstance(stats, Stats)
    assert stats.resolved == 12
    assert stats.open == 7
    assert stats.lifetime_reward_aigen_paid == 108000.25


# --------------------------------------------------------------------------- #
# A2A JSON-RPC
# --------------------------------------------------------------------------- #


@respx.mock
@pytest.mark.asyncio
async def test_a2a_message_send(client):
    def responder(request: httpx.Request) -> httpx.Response:
        import json as _json

        env = _json.loads(request.content)
        assert env["jsonrpc"] == "2.0"
        assert env["method"] == "message/send"
        assert env["params"] == {"message": {"role": "user", "text": "hi"}}
        assert isinstance(env["id"], int)
        return httpx.Response(
            200, json={"jsonrpc": "2.0", "id": env["id"], "result": {"task_id": "t-7"}}
        )

    respx.post(f"{BASE}/api/a2a").mock(side_effect=responder)
    result = await client.a2a_message_send({"role": "user", "text": "hi"})
    assert result == {"task_id": "t-7"}


@respx.mock
@pytest.mark.asyncio
async def test_a2a_tasks_list(client):
    respx.post(f"{BASE}/api/a2a").mock(
        return_value=httpx.Response(
            200, json={"jsonrpc": "2.0", "id": 1, "result": [{"id": "t-1"}, {"id": "t-2"}]}
        )
    )
    result = await client.a2a_tasks_list()
    assert [t["id"] for t in result] == ["t-1", "t-2"]


@respx.mock
@pytest.mark.asyncio
async def test_a2a_rpc_error_raises(client):
    respx.post(f"{BASE}/api/a2a").mock(
        return_value=httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32601, "message": "method not found", "data": {"x": 1}},
            },
        )
    )
    with pytest.raises(OABPRPCError) as exc:
        await client.a2a_call("nope")
    assert exc.value.code == -32601
    assert "method not found" in str(exc.value)
    assert exc.value.data == {"x": 1}


@respx.mock
@pytest.mark.asyncio
async def test_a2a_ids_are_unique(client):
    seen_ids = []

    def responder(request: httpx.Request) -> httpx.Response:
        import json as _json

        env = _json.loads(request.content)
        seen_ids.append(env["id"])
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": env["id"], "result": "ok"})

    respx.post(f"{BASE}/api/a2a").mock(side_effect=responder)
    await client.a2a_tasks_list()
    await client.a2a_tasks_list()
    await client.a2a_tasks_get("t-1")
    assert len(set(seen_ids)) == 3  # monotonically increasing, all distinct


# --------------------------------------------------------------------------- #
# error handling
# --------------------------------------------------------------------------- #


@respx.mock
@pytest.mark.asyncio
async def test_404_raises_not_found(client):
    respx.get(f"{BASE}/api/missions/ghost").mock(
        return_value=httpx.Response(404, json={"error": "mission not found"})
    )
    with pytest.raises(OABPNotFoundError) as exc:
        await client.get_mission("ghost")
    assert exc.value.status_code == 404
    assert "mission not found" in str(exc.value)
    assert exc.value.payload == {"error": "mission not found"}


@respx.mock
@pytest.mark.asyncio
async def test_400_raises_bad_request(client):
    respx.post(f"{BASE}/api/missions").mock(
        return_value=httpx.Response(400, json={"message": "deadline_hours must be positive"})
    )
    with pytest.raises(OABPBadRequestError) as exc:
        await client.create_mission(
            title="t", description="d", reward_amount=1,
            verification_type="oracle", deadline_hours=1,
        )
    assert exc.value.status_code == 400
    assert "deadline_hours" in str(exc.value)


@respx.mock
@pytest.mark.asyncio
async def test_429_raises_rate_limit_with_retry_after(client):
    respx.get(f"{BASE}/api/missions").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "12"}, json={"error": "slow down"})
    )
    with pytest.raises(OABPRateLimitError) as exc:
        await client.list_missions()
    assert exc.value.status_code == 429
    assert exc.value.retry_after == 12.0


@respx.mock
@pytest.mark.asyncio
async def test_500_raises_server_error(client):
    respx.get(f"{BASE}/api/stats").mock(return_value=httpx.Response(503, text="upstream down"))
    with pytest.raises(OABPServerError) as exc:
        await client.get_stats()
    assert exc.value.status_code == 503


@respx.mock
@pytest.mark.asyncio
async def test_transport_error_is_wrapped(client):
    respx.get(f"{BASE}/api/missions").mock(side_effect=httpx.ConnectError("no route"))
    with pytest.raises(OABPTransportError):
        await client.list_missions()


@pytest.mark.asyncio
async def test_config_errors():
    with pytest.raises(OABPConfigError):
        OABPClient(base_url="")

    c = OABPClient()  # no default agent_id
    try:
        with pytest.raises(OABPConfigError):
            await c.get_mission("")
        with pytest.raises(OABPConfigError):
            await c.create_mission(
                title="t", description="d", reward_amount=1,
                verification_type="oracle", deadline_hours=1,
            )  # missing creator
        with pytest.raises(OABPConfigError):
            await c.submit("m", proof="x")  # missing submitter
    finally:
        await c.aclose()


@pytest.mark.asyncio
async def test_use_after_close_raises():
    c = OABPClient(agent_id="a")
    await c.aclose()
    assert c.is_closed
    with pytest.raises(OABPConfigError):
        await c.list_missions()
    # double close is a no-op
    await c.aclose()


# --------------------------------------------------------------------------- #
# context manager
# --------------------------------------------------------------------------- #


@respx.mock
@pytest.mark.asyncio
async def test_async_context_manager_closes():
    respx.get(f"{BASE}/api/missions").mock(return_value=httpx.Response(200, json=[]))
    async with OABPClient(agent_id="ctx") as c:
        assert c.is_closed is False
        assert await c.list_missions() == []
    assert c.is_closed is True


@pytest.mark.asyncio
async def test_byo_client_not_closed_by_sdk():
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=[]))
    external = httpx.AsyncClient(base_url=BASE, transport=transport)
    try:
        async with OABPClient(client=external) as c:
            assert await c.list_missions() == []
        # SDK closed its wrapper but must NOT close a client it does not own
        assert external.is_closed is False
    finally:
        await external.aclose()


# --------------------------------------------------------------------------- #
# stream_open_missions  (async iterator)
# --------------------------------------------------------------------------- #


@respx.mock
@pytest.mark.asyncio
async def test_stream_yields_only_new_missions():
    # poll 1: [m1]            -> seeds seen-set, yields nothing (include_existing=False)
    # poll 2: [m1, m2]        -> yields m2
    # poll 3: [m1, m2, m3]    -> yields m3
    polls = [
        [sample_mission("m1")],
        [sample_mission("m1"), sample_mission("m2")],
        [sample_mission("m1"), sample_mission("m2"), sample_mission("m3")],
    ]
    call = {"n": 0}

    def responder(request: httpx.Request) -> httpx.Response:
        body = polls[min(call["n"], len(polls) - 1)]
        call["n"] += 1
        return httpx.Response(200, json=body)

    respx.get(f"{BASE}/api/missions").mock(side_effect=responder)

    seen_ids = []
    async with OABPClient(agent_id="streamer") as c:
        async for mission in c.stream_open_missions(poll_interval=0.001, max_iterations=3):
            seen_ids.append(mission.id)
    assert seen_ids == ["m2", "m3"]


@respx.mock
@pytest.mark.asyncio
async def test_stream_include_existing():
    respx.get(f"{BASE}/api/missions").mock(
        return_value=httpx.Response(200, json=[sample_mission("a"), sample_mission("b")])
    )
    out = []
    async with OABPClient(agent_id="s") as c:
        async for m in c.stream_open_missions(
            poll_interval=0.001, include_existing=True, max_iterations=1
        ):
            out.append(m.id)
    assert out == ["a", "b"]


@respx.mock
@pytest.mark.asyncio
async def test_stream_stop_event():
    respx.get(f"{BASE}/api/missions").mock(
        return_value=httpx.Response(200, json=[sample_mission("x")])
    )
    stop = asyncio.Event()
    collected = []

    async with OABPClient(agent_id="s") as c:
        agen = c.stream_open_missions(
            poll_interval=0.05, include_existing=True, stop_event=stop
        )
        async for m in agen:
            collected.append(m.id)
            stop.set()  # ask the stream to finish after this cycle
    assert collected == ["x"]


@pytest.mark.asyncio
async def test_stream_rejects_bad_interval():
    c = OABPClient(agent_id="s")
    try:
        with pytest.raises(OABPConfigError):
            agen = c.stream_open_missions(poll_interval=0)
            await agen.__anext__()
    finally:
        await c.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_stream_propagates_errors():
    # a rate-limit mid-stream must surface, not be swallowed
    respx.get(f"{BASE}/api/missions").mock(return_value=httpx.Response(429, json={"error": "stop"}))
    c = OABPClient(agent_id="s")
    try:
        with pytest.raises(OABPRateLimitError):
            async for _ in c.stream_open_missions(poll_interval=0.001, include_existing=True):
                pass
    finally:
        await c.aclose()


# --------------------------------------------------------------------------- #
# model edge cases
# --------------------------------------------------------------------------- #


def test_mission_requires_id():
    with pytest.raises(ValueError):
        Mission.from_dict({"title": "no id"})


def test_unknown_enum_values_preserved():
    m = Mission.from_dict(
        {
            "id": "x",
            "reward": {"amount": "1.5", "currency": "DOGE"},
            "verification_type": "captcha",
            "status": "frozen",
            "deadline": None,
            "submissions": [],
        }
    )
    assert m.reward.currency == "DOGE"  # preserved as str, not coerced
    assert m.verification_type == "captcha"
    assert m.status == "frozen"
    assert m.reward.amount == 1.5  # numeric string coerced to float
    assert m.deadline is None
    assert m.deadline_datetime is None
    # an explicit, non-"open" status (even an unrecognised one) is treated as
    # NOT open — we only consider a mission open when it actually says so.
    assert m.is_open is False


def test_is_open_falls_back_to_deadline_when_status_absent():
    # no status at all -> fall back to the deadline
    future = Mission.from_dict({"id": "f", "deadline": 4102444800, "submissions": []})
    assert future.is_open is True
    past = Mission.from_dict({"id": "p", "deadline": 1, "submissions": []})
    assert past.is_open is False
    # no status and no deadline -> optimistically open
    neither = Mission.from_dict({"id": "n", "submissions": []})
    assert neither.is_open is True


def test_seconds_remaining():
    m = Mission.from_dict({"id": "x", "deadline": 1000, "submissions": []})
    assert m.seconds_remaining(now=900) == 100
    assert m.seconds_remaining(now=1100) == -100
    m2 = Mission.from_dict({"id": "y", "submissions": []})
    assert m2.seconds_remaining() is None
