//! Error types for the OABP client.

use thiserror::Error;

/// Convenience alias for results returned by this crate.
pub type Result<T> = std::result::Result<T, Error>;

/// Every failure mode the OABP client can surface.
///
/// Variants distinguish transport failures ([`Error::Http`]), malformed bodies
/// ([`Error::Decode`]), non-2xx HTTP responses ([`Error::Api`]), JSON-RPC level
/// faults from the A2A endpoint ([`Error::Rpc`]), and bad configuration
/// ([`Error::InvalidBaseUrl`] / [`Error::InvalidConfig`]).
#[derive(Debug, Error)]
#[non_exhaustive]
pub enum Error {
    /// The underlying HTTP transport failed (DNS, TLS, connect, timeout, …).
    #[error("http transport error: {0}")]
    Http(#[from] reqwest::Error),

    /// The response body could not be deserialized into the expected type.
    #[error("failed to decode response body: {0}")]
    Decode(#[source] serde_json::Error),

    /// The server returned a non-success HTTP status.
    ///
    /// `body` holds the raw response text (often a JSON error envelope) to aid
    /// debugging without forcing the caller to model every server error shape.
    #[error("api returned status {status}: {body}")]
    Api {
        /// The HTTP status code.
        status: u16,
        /// Raw response body, truncated by the server if large.
        body: String,
    },

    /// The A2A JSON-RPC endpoint returned an `error` member.
    #[error("a2a json-rpc error {code}: {message}")]
    Rpc {
        /// JSON-RPC error code.
        code: i64,
        /// Human-readable error message.
        message: String,
        /// Optional structured `data` member from the RPC error object.
        data: Option<serde_json::Value>,
    },

    /// The supplied base URL was not a valid absolute URL.
    #[error("invalid base url: {0}")]
    InvalidBaseUrl(#[source] url::ParseError),

    /// The client configuration was internally inconsistent.
    #[error("invalid client configuration: {0}")]
    InvalidConfig(String),
}

impl Error {
    /// Returns the HTTP status code, if this error originated from an HTTP
    /// response (either [`Error::Api`] or a status carried by [`Error::Http`]).
    #[must_use]
    pub fn status(&self) -> Option<u16> {
        match self {
            Error::Api { status, .. } => Some(*status),
            Error::Http(e) => e.status().map(|s| s.as_u16()),
            _ => None,
        }
    }

    /// True if this is a 4xx client error reported by the API.
    #[must_use]
    pub fn is_client_error(&self) -> bool {
        matches!(self.status(), Some(s) if (400..500).contains(&s))
    }
}
