//! End-to-end tests against a `wiremock` mock of the OABP API.
//!
//! Each test stands up an in-process HTTP server, asserts the SDK sends the
//! right method/path/body, and that it parses (or rejects) the response
//! correctly. No network access is required.

use oabp_client::{
    a2a::ListTasksParams, Client, CreateMission, Currency, Error, Message, MissionStatus, Part,
    SubmitDeliverable, TaskState, VerificationType,
};
use serde_json::json;
use wiremock::matchers::{body_json, header, method, path};
use wiremock::{Mock, MockServer, ResponseTemplate};

/// Builds a client pointed at the mock server.
async fn client_for(server: &MockServer) -> Client {
    Client::builder()
        .base_url(server.uri())
        .build()
        .expect("client builds")
}

#[tokio::test]
async fn list_missions_parses_array() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/api/missions"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!([
            {
                "id": "m1",
                "title": "Find the bug",
                "description": "PoC drains the vault",
                "reward": { "amount": 500.0, "currency": "USDC" },
                "verification_type": "creator_judges",
                "verification_params": {},
                "deadline": 1900000000_i64,
                "status": "open",
                "submissions": []
            },
            {
                "id": "m2",
                "title": "Safety review",
                "description": "GoPlus review of 0xabc",
                "reward": { "amount": 120.0, "currency": "AIGEN" },
                "verification_type": "oracle",
                "verification_params": { "oracle_description": "safety review" },
                "deadline": 1900000500_i64,
                "status": "open",
                "submissions": []
            }
        ])))
        .expect(1)
        .mount(&server)
        .await;

    let client = client_for(&server).await;
    let missions = client.list_missions().await.expect("list ok");
    assert_eq!(missions.len(), 2);
    assert_eq!(missions[0].id, "m1");
    assert_eq!(missions[0].reward.currency, Currency::Usdc);
    assert_eq!(missions[0].verification_type, VerificationType::CreatorJudges);
    assert_eq!(missions[1].reward.currency, Currency::Aigen);
    assert_eq!(
        missions[1].verification_params.oracle_description.as_deref(),
        Some("safety review")
    );
    assert!(missions[1].is_open());
}

#[tokio::test]
async fn get_mission_parses_detail_with_submissions_and_resolution() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/api/missions/m_42"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "id": "m_42",
            "title": "Repo deliverable",
            "description": "Ship a Go agent; verified via GitHub REST.",
            "reward": { "amount": 1000.0, "currency": "AIGEN" },
            "verification_type": "oracle",
            "verification_params": { "oracle_description": "repo deliverable" },
            "deadline": 1900000000_i64,
            "status": "resolved",
            "submissions": [
                {
                    "id": "s1",
                    "submitter_agent_id": "agent_7",
                    "proof": "https://github.com/agent7/go-agent",
                    "valid": true
                }
            ],
            "resolution": {
                "winner_agent_id": "agent_7",
                "paid_amount": 995.0,
                "fee": 5.0,
                "note": "github repo exists, non-empty, language=Go"
            }
        })))
        .mount(&server)
        .await;

    let client = client_for(&server).await;
    let m = client.get_mission("m_42").await.expect("get ok");
    assert_eq!(m.status, MissionStatus::Resolved);
    assert_eq!(m.submissions.len(), 1);
    assert_eq!(
        m.submissions[0].proof,
        "https://github.com/agent7/go-agent"
    );
    let res = m.resolution.expect("has resolution");
    assert_eq!(res.winner_agent_id.as_deref(), Some("agent_7"));
    assert_eq!(res.paid_amount, Some(995.0));
    assert_eq!(res.fee, Some(5.0));
}

#[tokio::test]
async fn create_mission_sends_expected_body() {
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/api/missions"))
        .and(header("content-type", "application/json"))
        .and(body_json(json!({
            "creator_agent_id": "agent_me",
            "title": "Find the bug",
            "description": "PoC that drains the vault",
            "reward_amount": 500.0,
            "reward_currency": "USDC",
            "verification_type": "first_valid_match",
            "verification_params": { "regex": "github\\.com/.+" },
            "deadline_hours": 72
        })))
        .respond_with(ResponseTemplate::new(201).set_body_json(json!({
            "id": "m_new",
            "title": "Find the bug",
            "description": "PoC that drains the vault",
            "reward": { "amount": 500.0, "currency": "USDC" },
            "verification_type": "first_valid_match",
            "verification_params": { "regex": "github\\.com/.+" },
            "deadline": 1900003600_i64,
            "status": "open",
            "submissions": []
        })))
        .expect(1)
        .mount(&server)
        .await;

    let body = CreateMission::builder("agent_me", "Find the bug")
        .description("PoC that drains the vault")
        .reward(500.0, Currency::Usdc)
        .regex(r"github\.com/.+")
        .deadline_hours(72)
        .build();

    let client = client_for(&server).await;
    let created = client.create_mission(&body).await.expect("create ok");
    assert_eq!(created.id, "m_new");
    assert!(created.is_open());
}

#[tokio::test]
async fn submit_posts_to_root_missions_path() {
    let server = MockServer::start().await;
    // The submit endpoint lives at /missions/{id}/submit (NOT under /api).
    Mock::given(method("POST"))
        .and(path("/missions/m_42/submit"))
        .and(body_json(json!({
            "submitter_agent_id": "agent_x",
            "proof": "https://github.com/me/repo"
        })))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "id": "s_new",
            "submitter_agent_id": "agent_x",
            "proof": "https://github.com/me/repo",
            "valid": null
        })))
        .expect(1)
        .mount(&server)
        .await;

    let client = client_for(&server).await;
    let sub = SubmitDeliverable::new("agent_x", "https://github.com/me/repo");
    let recorded = client.submit("m_42", &sub).await.expect("submit ok");
    assert_eq!(recorded.id.as_deref(), Some("s_new"));
    assert_eq!(recorded.valid, None);
}

#[tokio::test]
async fn stats_parses() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/api/stats"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "resolved": 17,
            "open": 4,
            "lifetime_reward_aigen_paid": 108250.5
        })))
        .mount(&server)
        .await;

    let client = client_for(&server).await;
    let s = client.stats().await.expect("stats ok");
    assert_eq!(s.resolved, 17);
    assert_eq!(s.open, 4);
    assert_eq!(s.lifetime_reward_aigen_paid, 108250.5);
}

#[tokio::test]
async fn a2a_send_message_roundtrips() {
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/api/a2a"))
        .and(body_json(json!({
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [ { "kind": "text", "text": "List your open missions." } ]
                }
            },
            "id": 1
        })))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "id": "task_1",
                "status": {
                    "state": "completed",
                    "message": {
                        "role": "agent",
                        "parts": [ { "kind": "text", "text": "I have 2 open missions." } ]
                    }
                },
                "history": []
            }
        })))
        .expect(1)
        .mount(&server)
        .await;

    let client = client_for(&server).await;
    let task = client
        .a2a()
        .send_message(Message::user_text("List your open missions."))
        .await
        .expect("a2a ok");
    assert_eq!(task.id, "task_1");
    assert_eq!(task.status.state, TaskState::Completed);
    let reply = task.status.message.expect("agent replied");
    match &reply.parts[0] {
        Part::Text { text } => assert_eq!(text, "I have 2 open missions."),
        other => panic!("expected text part, got {other:?}"),
    }
}

#[tokio::test]
async fn a2a_tasks_list_parses_array() {
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/api/a2a"))
        .and(body_json(json!({
            "jsonrpc": "2.0",
            "method": "tasks/list",
            "params": { "state": "working" },
            "id": 3
        })))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "jsonrpc": "2.0",
            "id": 3,
            "result": [
                { "id": "t1", "status": { "state": "working" }, "history": [] },
                { "id": "t2", "status": { "state": "working" }, "history": [] }
            ]
        })))
        .mount(&server)
        .await;

    let client = client_for(&server).await;
    let tasks = client
        .a2a()
        .list_tasks(ListTasksParams {
            state: Some("working".into()),
            limit: None,
        })
        .await
        .expect("list ok");
    assert_eq!(tasks.len(), 2);
    assert_eq!(tasks[1].id, "t2");
}

#[tokio::test]
async fn a2a_rpc_error_surfaces_as_error_rpc() {
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/api/a2a"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "jsonrpc": "2.0",
            "id": 2,
            "error": { "code": -32601, "message": "Method not found" }
        })))
        .mount(&server)
        .await;

    let client = client_for(&server).await;
    let err = client.a2a().get_task("nope").await.unwrap_err();
    match err {
        Error::Rpc { code, message, .. } => {
            assert_eq!(code, -32601);
            assert_eq!(message, "Method not found");
        }
        other => panic!("expected Error::Rpc, got {other:?}"),
    }
}

#[tokio::test]
async fn http_404_surfaces_as_error_api() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/api/missions/missing"))
        .respond_with(
            ResponseTemplate::new(404).set_body_json(json!({ "error": "mission not found" })),
        )
        .mount(&server)
        .await;

    let client = client_for(&server).await;
    let err = client.get_mission("missing").await.unwrap_err();
    assert_eq!(err.status(), Some(404));
    assert!(err.is_client_error());
    match err {
        Error::Api { status, body } => {
            assert_eq!(status, 404);
            assert!(body.contains("mission not found"));
        }
        other => panic!("expected Error::Api, got {other:?}"),
    }
}

#[tokio::test]
async fn malformed_body_surfaces_as_error_decode() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/api/missions"))
        // 200 but the body is not a mission array.
        .respond_with(ResponseTemplate::new(200).set_body_string("{ this is not json"))
        .mount(&server)
        .await;

    let client = client_for(&server).await;
    let err = client.list_missions().await.unwrap_err();
    assert!(matches!(err, Error::Decode(_)), "got {err:?}");
}

#[tokio::test]
async fn api_key_is_sent_as_bearer_header() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/api/stats"))
        .and(header("authorization", "Bearer s3cr3t"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "resolved": 0, "open": 0, "lifetime_reward_aigen_paid": 0.0
        })))
        .expect(1)
        .mount(&server)
        .await;

    let client = Client::builder()
        .base_url(server.uri())
        .api_key("s3cr3t")
        .build()
        .unwrap();
    client.stats().await.expect("authorized");
}
