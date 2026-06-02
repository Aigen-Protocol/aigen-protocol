"""Tests for the A2A JSON-RPC methods (message/send, tasks/get, tasks/list)."""

from __future__ import annotations

import pytest

from oabp_a2a import A2AClient, JSONRPCError
from tests.conftest import BASE_URL, MockResponse


def make_client(session):
    return A2AClient(base_url=BASE_URL, agent_id="agent-007", session=session)


# --------------------------------------------------------------------------- #
# message/send
# --------------------------------------------------------------------------- #
def test_send_message_builds_correct_envelope(session):
    captured = {}

    def handler(req):
        captured["body"] = req.json
        return MockResponse(
            200,
            json_body={
                "jsonrpc": "2.0",
                "id": req.json["id"],
                "result": {
                    "id": "task-1",
                    "contextId": "ctx-1",
                    "status": {"state": "completed"},
                    "history": [
                        {"role": "user", "parts": [{"kind": "text", "text": "hello"}]},
                        {"role": "agent", "parts": [{"kind": "text", "text": "hi back"}]},
                    ],
                },
            },
        )

    session.route("POST", "/api/a2a", handler)
    client = make_client(session)

    task = client.send_message("hello")

    body = captured["body"]
    assert body["jsonrpc"] == "2.0"
    assert body["method"] == "message/send"
    msg = body["params"]["message"]
    assert msg["role"] == "user"
    assert msg["parts"][0] == {"kind": "text", "text": "hello"}
    assert msg["agentId"] == "agent-007"
    assert "messageId" in msg

    assert task.id == "task-1"
    assert task.context_id == "ctx-1"
    assert task.status_state == "completed"
    assert task.history[-1].text == "hi back"


def test_send_message_continues_task(session):
    captured = {}

    def handler(req):
        captured["body"] = req.json
        return MockResponse(
            200,
            json_body={
                "jsonrpc": "2.0",
                "id": req.json["id"],
                "result": {"id": "task-1", "status": {"state": "working"}},
            },
        )

    session.route("POST", "/api/a2a", handler)
    client = make_client(session)
    client.send_message("more", task_id="task-1", context_id="ctx-1")

    msg = captured["body"]["params"]["message"]
    assert msg["taskId"] == "task-1"
    assert msg["contextId"] == "ctx-1"


def test_send_message_returning_bare_message_is_wrapped(session):
    session.route(
        "POST",
        "/api/a2a",
        lambda req: MockResponse(
            200,
            json_body={
                "jsonrpc": "2.0",
                "id": req.json["id"],
                "result": {
                    "kind": "message",
                    "role": "agent",
                    "parts": [{"kind": "text", "text": "pong"}],
                },
            },
        ),
    )
    client = make_client(session)
    task = client.send_message("ping")
    assert task.history[0].text == "pong"
    assert task.status_state == "completed"


# --------------------------------------------------------------------------- #
# tasks/get
# --------------------------------------------------------------------------- #
def test_get_task(session):
    captured = {}

    def handler(req):
        captured["body"] = req.json
        return MockResponse(
            200,
            json_body={
                "jsonrpc": "2.0",
                "id": req.json["id"],
                "result": {
                    "id": "task-42",
                    "status": {"state": "completed"},
                    "history": [
                        {"role": "agent", "parts": [{"kind": "text", "text": "done"}]}
                    ],
                    "artifacts": [{"name": "out.txt", "parts": []}],
                },
            },
        )

    session.route("POST", "/api/a2a", handler)
    client = make_client(session)
    task = client.get_task("task-42", history_length=5)

    assert captured["body"]["method"] == "tasks/get"
    assert captured["body"]["params"] == {"id": "task-42", "historyLength": 5}
    assert task.id == "task-42"
    assert task.artifacts[0]["name"] == "out.txt"


# --------------------------------------------------------------------------- #
# tasks/list
# --------------------------------------------------------------------------- #
def test_list_tasks_array_response(session):
    session.route(
        "POST",
        "/api/a2a",
        lambda req: MockResponse(
            200,
            json_body={
                "jsonrpc": "2.0",
                "id": req.json["id"],
                "result": [
                    {"id": "t1", "status": {"state": "completed"}},
                    {"id": "t2", "status": {"state": "working"}},
                ],
            },
        ),
    )
    client = make_client(session)
    tasks = client.list_tasks(length=10)
    assert [t.id for t in tasks] == ["t1", "t2"]
    assert tasks[1].status_state == "working"


def test_list_tasks_wrapped_response(session):
    session.route(
        "POST",
        "/api/a2a",
        lambda req: MockResponse(
            200,
            json_body={
                "jsonrpc": "2.0",
                "id": req.json["id"],
                "result": {"tasks": [{"id": "t9", "status": {"state": "failed"}}]},
            },
        ),
    )
    client = make_client(session)
    tasks = client.list_tasks()
    assert tasks[0].id == "t9"
    assert tasks[0].status_state == "failed"


# --------------------------------------------------------------------------- #
# error handling
# --------------------------------------------------------------------------- #
def test_jsonrpc_error_raised(session):
    session.route(
        "POST",
        "/api/a2a",
        lambda req: MockResponse(
            200,
            json_body={
                "jsonrpc": "2.0",
                "id": req.json["id"],
                "error": {"code": -32601, "message": "Method not found"},
            },
        ),
    )
    client = make_client(session)
    with pytest.raises(JSONRPCError) as exc:
        client.get_task("nope")
    assert exc.value.code == -32601
    assert "Method not found" in str(exc.value)


def test_unique_request_ids(session):
    seen = []

    def handler(req):
        seen.append(req.json["id"])
        return MockResponse(
            200,
            json_body={"jsonrpc": "2.0", "id": req.json["id"], "result": []},
        )

    session.route("POST", "/api/a2a", handler)
    client = make_client(session)
    client.list_tasks()
    client.list_tasks()
    assert seen[0] != seen[1]
