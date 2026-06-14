//! A2A (Agent-to-Agent) JSON-RPC 2.0 envelope types for `POST /api/a2a`.
//!
//! The OABP A2A endpoint speaks JSON-RPC 2.0. This module models the request
//! envelope, the success/error response, and the parameter shapes for the three
//! supported methods (`message/send`, `tasks/get`, `tasks/list`). The high-level
//! [`crate::Client::a2a`] surface wraps these so callers rarely build envelopes
//! by hand, but they are public for advanced use.

use crate::models::Message;
use serde::{Deserialize, Serialize};

/// A JSON-RPC 2.0 request envelope.
#[derive(Debug, Clone, Serialize)]
pub struct RpcRequest<'a, P: Serialize> {
    /// Always `"2.0"`.
    pub jsonrpc: &'static str,
    /// The method name (e.g. `"message/send"`).
    pub method: &'a str,
    /// Method parameters.
    pub params: P,
    /// Correlation id echoed back in the response.
    pub id: u64,
}

impl<'a, P: Serialize> RpcRequest<'a, P> {
    /// Builds a request with `jsonrpc` pinned to `"2.0"`.
    #[must_use]
    pub fn new(method: &'a str, params: P, id: u64) -> Self {
        RpcRequest {
            jsonrpc: "2.0",
            method,
            params,
            id,
        }
    }
}

/// The `error` member of a JSON-RPC response.
#[derive(Debug, Clone, Deserialize)]
pub struct RpcError {
    /// Numeric error code.
    pub code: i64,
    /// Human-readable message.
    pub message: String,
    /// Optional structured data.
    #[serde(default)]
    pub data: Option<serde_json::Value>,
}

/// A JSON-RPC 2.0 response envelope. Exactly one of `result` / `error` is set.
///
/// The explicit `bound` keeps serde from inferring a spurious `R: Default`
/// requirement from the `#[serde(default)]` on the `Option<R>` field.
#[derive(Debug, Clone, Deserialize)]
#[serde(bound(deserialize = "R: Deserialize<'de>"))]
pub struct RpcResponse<R> {
    /// The id echoed from the request.
    #[serde(default)]
    pub id: Option<serde_json::Value>,
    /// Present on success.
    #[serde(default)]
    pub result: Option<R>,
    /// Present on failure.
    #[serde(default)]
    pub error: Option<RpcError>,
}

/// Parameters for the `message/send` method.
#[derive(Debug, Clone, Serialize)]
pub struct SendMessageParams {
    /// The message to deliver to the remote agent.
    pub message: Message,
}

/// Parameters for the `tasks/get` method.
#[derive(Debug, Clone, Serialize)]
pub struct GetTaskParams {
    /// The task id to fetch.
    pub id: String,
}

/// Parameters for the `tasks/list` method.
///
/// All fields are optional filters; an empty value lists everything the caller
/// is permitted to see.
#[derive(Debug, Clone, Default, Serialize)]
pub struct ListTasksParams {
    /// Restrict to a single task state, when set.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub state: Option<String>,
    /// Cap the number of returned tasks, when set.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub limit: Option<u32>,
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::{Role, Task};

    #[test]
    fn request_envelope_pins_version() {
        let req = RpcRequest::new(
            "message/send",
            SendMessageParams {
                message: Message::user_text("hello agent"),
            },
            1,
        );
        let v = serde_json::to_value(&req).unwrap();
        assert_eq!(v["jsonrpc"], "2.0");
        assert_eq!(v["method"], "message/send");
        assert_eq!(v["id"], 1);
        assert_eq!(v["params"]["message"]["role"], "user");
        assert_eq!(v["params"]["message"]["parts"][0]["text"], "hello agent");
    }

    #[test]
    fn success_response_parses_task_result() {
        let raw = r#"{
            "jsonrpc":"2.0","id":1,
            "result":{"id":"t9","status":{"state":"completed"},"history":[]}
        }"#;
        let resp: RpcResponse<Task> = serde_json::from_str(raw).unwrap();
        assert!(resp.error.is_none());
        let task = resp.result.unwrap();
        assert_eq!(task.id, "t9");
    }

    #[test]
    fn error_response_parses() {
        let raw = r#"{"jsonrpc":"2.0","id":1,
            "error":{"code":-32601,"message":"Method not found"}}"#;
        let resp: RpcResponse<Task> = serde_json::from_str(raw).unwrap();
        assert!(resp.result.is_none());
        let e = resp.error.unwrap();
        assert_eq!(e.code, -32601);
        assert_eq!(e.message, "Method not found");
    }

    #[test]
    fn list_params_omit_unset_filters() {
        let v = serde_json::to_value(ListTasksParams::default()).unwrap();
        assert_eq!(v, serde_json::json!({}));
        let v2 = serde_json::to_value(ListTasksParams {
            state: Some("working".into()),
            limit: Some(10),
        })
        .unwrap();
        assert_eq!(v2["state"], "working");
        assert_eq!(v2["limit"], 10);
    }

    #[test]
    fn message_default_role_constructor() {
        let m = Message::user_text("x");
        assert_eq!(m.role, Role::User);
    }
}
