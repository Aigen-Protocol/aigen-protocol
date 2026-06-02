//! The async [`Client`] and its [`ClientBuilder`].

use std::time::Duration;

use reqwest::{header, Method, StatusCode};
use serde::de::DeserializeOwned;
use serde::Serialize;
use url::Url;

use crate::a2a::{
    GetTaskParams, ListTasksParams, RpcRequest, RpcResponse, SendMessageParams,
};
use crate::error::{Error, Result};
use crate::models::{Message, Mission, Stats, Submission, Task};
use crate::requests::{CreateMission, SubmitDeliverable};

/// Default base URL of the public OABP / AIGEN deployment.
pub const DEFAULT_BASE_URL: &str = "https://cryptogenesis.duckdns.org";

/// Builder for [`Client`].
///
/// Obtain one via [`Client::builder`]. Every setter is optional; sensible
/// defaults are applied (the public base URL, a 30s timeout, a descriptive
/// `User-Agent`). Call [`ClientBuilder::build`] to finalize.
///
/// ```
/// use oabp_client::Client;
/// use std::time::Duration;
///
/// let client = Client::builder()
///     .base_url("https://cryptogenesis.duckdns.org")
///     .timeout(Duration::from_secs(10))
///     .api_key("secret-token")
///     .build()
///     .expect("valid config");
/// let _ = client; // ready to use
/// ```
#[derive(Debug, Clone)]
pub struct ClientBuilder {
    base_url: String,
    timeout: Duration,
    user_agent: String,
    api_key: Option<String>,
    /// Optional pre-built reqwest client, for callers who need full control
    /// (proxies, custom TLS, connection pools).
    inner: Option<reqwest::Client>,
}

impl Default for ClientBuilder {
    fn default() -> Self {
        ClientBuilder {
            base_url: DEFAULT_BASE_URL.to_string(),
            timeout: Duration::from_secs(30),
            user_agent: concat!("oabp-client/", env!("CARGO_PKG_VERSION")).to_string(),
            api_key: None,
            inner: None,
        }
    }
}

impl ClientBuilder {
    /// Overrides the API base URL (default: [`DEFAULT_BASE_URL`]).
    #[must_use]
    pub fn base_url(mut self, url: impl Into<String>) -> Self {
        self.base_url = url.into();
        self
    }

    /// Sets the per-request timeout (default: 30s). Ignored if a fully built
    /// reqwest client is supplied via [`ClientBuilder::reqwest_client`].
    #[must_use]
    pub fn timeout(mut self, timeout: Duration) -> Self {
        self.timeout = timeout;
        self
    }

    /// Sets the `User-Agent` header.
    #[must_use]
    pub fn user_agent(mut self, ua: impl Into<String>) -> Self {
        self.user_agent = ua.into();
        self
    }

    /// Attaches a bearer token, sent as `Authorization: Bearer <key>` on every
    /// request. Optional — the public API is largely permissionless.
    #[must_use]
    pub fn api_key(mut self, key: impl Into<String>) -> Self {
        self.api_key = Some(key.into());
        self
    }

    /// Supplies a pre-configured [`reqwest::Client`], bypassing the builder's
    /// own timeout/UA construction (those are then assumed baked into it).
    #[must_use]
    pub fn reqwest_client(mut self, client: reqwest::Client) -> Self {
        self.inner = Some(client);
        self
    }

    /// Validates configuration and constructs the [`Client`].
    ///
    /// # Errors
    /// Returns [`Error::InvalidBaseUrl`] if the base URL is not absolute, or
    /// [`Error::Http`] if the internal reqwest client fails to build.
    pub fn build(self) -> Result<Client> {
        // Parse + normalize the base URL up front so every later `join` is
        // infallible-ish and relative-path joins behave (trailing slash).
        let mut base = Url::parse(&self.base_url).map_err(Error::InvalidBaseUrl)?;
        if base.cannot_be_a_base() {
            return Err(Error::InvalidConfig(format!(
                "base url '{}' cannot be a base",
                self.base_url
            )));
        }
        // Ensure the path ends in '/' so `Url::join("api/missions")` appends
        // rather than replacing the final path segment.
        if !base.path().ends_with('/') {
            let p = format!("{}/", base.path());
            base.set_path(&p);
        }

        let http = match self.inner {
            Some(c) => c,
            None => {
                let mut headers = header::HeaderMap::new();
                if let Some(key) = &self.api_key {
                    let mut val = header::HeaderValue::from_str(&format!("Bearer {key}"))
                        .map_err(|_| {
                            Error::InvalidConfig("api key contains invalid header bytes".into())
                        })?;
                    val.set_sensitive(true);
                    headers.insert(header::AUTHORIZATION, val);
                }
                reqwest::Client::builder()
                    .timeout(self.timeout)
                    .user_agent(self.user_agent.clone())
                    .default_headers(headers)
                    .build()?
            }
        };

        Ok(Client { http, base })
    }
}

/// An async client for the OABP / AIGEN protocol HTTP API.
///
/// Cheap to clone (the inner [`reqwest::Client`] is reference-counted and shares
/// a connection pool), so clone freely across tasks rather than wrapping in an
/// `Arc`. All methods are `async` and require a Tokio runtime; for synchronous
/// contexts enable the `blocking` feature and use `oabp_client::blocking::Client`.
#[derive(Debug, Clone)]
pub struct Client {
    http: reqwest::Client,
    base: Url,
}

impl Client {
    /// Starts building a client. See [`ClientBuilder`].
    #[must_use]
    pub fn builder() -> ClientBuilder {
        ClientBuilder::default()
    }

    /// Builds a client against [`DEFAULT_BASE_URL`] with all defaults.
    ///
    /// # Errors
    /// Propagates [`ClientBuilder::build`] errors (only on a broken transport).
    pub fn new() -> Result<Self> {
        ClientBuilder::default().build()
    }

    /// The effective base URL (always ends in `/`).
    #[must_use]
    pub fn base_url(&self) -> &str {
        self.base.as_str()
    }

    // ---- Mission endpoints ------------------------------------------------

    /// `GET /api/missions` — list the currently open missions.
    ///
    /// # Errors
    /// [`Error::Http`] on transport failure, [`Error::Api`] on a non-2xx
    /// status, or [`Error::Decode`] if the body is not a JSON mission array.
    pub async fn list_missions(&self) -> Result<Vec<Mission>> {
        self.send_json(Method::GET, "api/missions", None::<()>).await
    }

    /// `GET /api/missions/{id}` — fetch a single mission with its submissions
    /// and resolution.
    ///
    /// # Errors
    /// As [`Client::list_missions`]; a 404 surfaces as [`Error::Api`] with
    /// `status == 404`.
    pub async fn get_mission(&self, id: &str) -> Result<Mission> {
        let path = format!("api/missions/{}", urlencode_segment(id));
        self.send_json(Method::GET, &path, None::<()>).await
    }

    /// `POST /api/missions` — create a new mission.
    ///
    /// Returns the created [`Mission`] as echoed by the server.
    ///
    /// # Errors
    /// As above; validation failures surface as [`Error::Api`] (4xx).
    pub async fn create_mission(&self, body: &CreateMission) -> Result<Mission> {
        self.send_json(Method::POST, "api/missions", Some(body)).await
    }

    /// `POST /missions/{id}/submit` — submit a deliverable to a mission.
    ///
    /// `proof` is text or a URL; the mission's verifier (regex for
    /// `first_valid_match`, or a GoPlus / GitHub oracle) adjudicates it. Returns
    /// the recorded [`Submission`].
    ///
    /// # Errors
    /// As above.
    pub async fn submit(&self, mission_id: &str, body: &SubmitDeliverable) -> Result<Submission> {
        // Note: this endpoint lives at the root (`/missions/...`), not under
        // `/api`, per the protocol spec.
        let path = format!("missions/{}/submit", urlencode_segment(mission_id));
        self.send_json(Method::POST, &path, Some(body)).await
    }

    /// `GET /api/stats` — protocol-wide counters.
    ///
    /// # Errors
    /// As [`Client::list_missions`].
    pub async fn stats(&self) -> Result<Stats> {
        self.send_json(Method::GET, "api/stats", None::<()>).await
    }

    /// Returns a handle to the A2A JSON-RPC surface (`POST /api/a2a`).
    #[must_use]
    pub fn a2a(&self) -> A2a<'_> {
        A2a { client: self }
    }

    // ---- internals --------------------------------------------------------

    /// Issues a request and decodes a JSON body of type `T`.
    ///
    /// Centralizes URL joining, optional body serialization, status handling,
    /// and the read-then-decode dance (so a non-2xx body can be captured as
    /// text for [`Error::Api`] regardless of content type).
    async fn send_json<T, B>(&self, method: Method, path: &str, body: Option<B>) -> Result<T>
    where
        T: DeserializeOwned,
        B: Serialize,
    {
        let resp = self.send_raw(method, path, body).await?;
        let status = resp.status();
        let bytes = resp.bytes().await?;

        if !status.is_success() {
            return Err(Error::Api {
                status: status.as_u16(),
                body: String::from_utf8_lossy(&bytes).into_owned(),
            });
        }
        serde_json::from_slice::<T>(&bytes).map_err(Error::Decode)
    }

    /// Builds + sends a request, returning the raw response. Shared by JSON and
    /// A2A paths.
    async fn send_raw<B>(
        &self,
        method: Method,
        path: &str,
        body: Option<B>,
    ) -> Result<reqwest::Response>
    where
        B: Serialize,
    {
        let url = self
            .base
            .join(path)
            .map_err(Error::InvalidBaseUrl)?;
        let mut req = self.http.request(method, url);
        if let Some(b) = body {
            req = req.json(&b);
        }
        Ok(req.send().await?)
    }

    /// Low-level A2A JSON-RPC call. Sends one request envelope and unwraps the
    /// response into either the typed `result` or an [`Error::Rpc`].
    async fn rpc<P, R>(&self, method: &str, params: P, id: u64) -> Result<R>
    where
        P: Serialize,
        R: DeserializeOwned,
    {
        let envelope = RpcRequest::new(method, params, id);
        let resp = self.send_raw(Method::POST, "api/a2a", Some(envelope)).await?;
        let status = resp.status();
        let bytes = resp.bytes().await?;

        // A JSON-RPC server may still signal transport-level problems via HTTP
        // status; surface those before attempting to parse an envelope, except
        // for 200 where the error lives inside the body.
        if status != StatusCode::OK && !status.is_success() {
            return Err(Error::Api {
                status: status.as_u16(),
                body: String::from_utf8_lossy(&bytes).into_owned(),
            });
        }

        let parsed: RpcResponse<R> = serde_json::from_slice(&bytes).map_err(Error::Decode)?;
        if let Some(err) = parsed.error {
            return Err(Error::Rpc {
                code: err.code,
                message: err.message,
                data: err.data,
            });
        }
        parsed.result.ok_or_else(|| Error::Rpc {
            code: 0,
            message: "json-rpc response had neither result nor error".into(),
            data: None,
        })
    }
}

/// A2A JSON-RPC sub-API, borrowed from a [`Client`] via [`Client::a2a`].
///
/// Methods map 1:1 to the JSON-RPC methods exposed at `POST /api/a2a`.
#[derive(Debug, Clone, Copy)]
pub struct A2a<'c> {
    client: &'c Client,
}

impl A2a<'_> {
    /// `message/send` — deliver a [`Message`] to the remote agent and receive
    /// the resulting [`Task`].
    ///
    /// # Errors
    /// [`Error::Rpc`] if the agent returns a JSON-RPC error; otherwise as the
    /// HTTP methods.
    pub async fn send_message(&self, message: Message) -> Result<Task> {
        self.client
            .rpc("message/send", SendMessageParams { message }, 1)
            .await
    }

    /// Convenience wrapper: send a single line of user text and return the task.
    ///
    /// # Errors
    /// As [`A2a::send_message`].
    pub async fn send_text(&self, text: impl Into<String>) -> Result<Task> {
        self.send_message(Message::user_text(text)).await
    }

    /// `tasks/get` — fetch a task by id.
    ///
    /// # Errors
    /// As [`A2a::send_message`].
    pub async fn get_task(&self, id: impl Into<String>) -> Result<Task> {
        self.client
            .rpc("tasks/get", GetTaskParams { id: id.into() }, 2)
            .await
    }

    /// `tasks/list` — list tasks, optionally filtered.
    ///
    /// # Errors
    /// As [`A2a::send_message`].
    pub async fn list_tasks(&self, params: ListTasksParams) -> Result<Vec<Task>> {
        self.client.rpc("tasks/list", params, 3).await
    }
}

/// Percent-encodes a single path segment so ids with slashes/spaces don't break
/// out of their position in the URL. Conservative allowlist (RFC 3986
/// unreserved); everything else is `%`-escaped.
fn urlencode_segment(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for b in s.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'.' | b'_' | b'~' => {
                out.push(b as char);
            }
            other => {
                out.push('%');
                out.push(char::from_digit((other >> 4) as u32, 16).unwrap().to_ascii_uppercase());
                out.push(char::from_digit((other & 0xf) as u32, 16).unwrap().to_ascii_uppercase());
            }
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn builder_normalizes_base_url_trailing_slash() {
        let c = Client::builder()
            .base_url("https://example.com/api-root")
            .build()
            .unwrap();
        assert!(c.base_url().ends_with('/'));
        // Join keeps the root prefix rather than replacing the last segment.
        let joined = c.base.join("api/missions").unwrap();
        assert_eq!(joined.path(), "/api-root/api/missions");
    }

    #[test]
    fn builder_rejects_relative_base_url() {
        let err = Client::builder().base_url("not a url").build().unwrap_err();
        assert!(matches!(err, Error::InvalidBaseUrl(_)));
    }

    #[test]
    fn default_base_url_applied() {
        let c = Client::new().unwrap();
        assert_eq!(c.base_url(), "https://cryptogenesis.duckdns.org/");
    }

    #[test]
    fn segment_encoding_escapes_unsafe_chars() {
        assert_eq!(urlencode_segment("m_42"), "m_42");
        assert_eq!(urlencode_segment("a/b c"), "a%2Fb%20c");
        assert_eq!(urlencode_segment("x?y#z"), "x%3Fy%23z");
    }
}
