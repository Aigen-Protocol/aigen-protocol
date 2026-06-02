//! Synchronous facade over the async [`crate::Client`], gated behind the
//! `blocking` feature.
//!
//! This is a thin convenience for synchronous call sites (CLIs, scripts, tests
//! that don't want an async runtime). Each method drives the async client on a
//! private current-thread Tokio runtime owned by the blocking [`Client`].
//!
//! ```no_run
//! # #[cfg(feature = "blocking")]
//! # fn main() -> Result<(), oabp_client::Error> {
//! use oabp_client::blocking::Client;
//!
//! let client = Client::new()?;
//! let missions = client.list_missions()?;
//! println!("{} open missions", missions.len());
//! # Ok(()) }
//! # #[cfg(not(feature = "blocking"))] fn main() {}
//! ```
//!
//! Do **not** call these methods from within an existing async runtime — block
//! the work on a dedicated thread instead. Inside async code, use the async
//! [`crate::Client`] directly.

use std::time::Duration;

use tokio::runtime::{Builder as RuntimeBuilder, Runtime};

use crate::client::{Client as AsyncClient, ClientBuilder as AsyncBuilder};
use crate::error::{Error, Result};
use crate::models::{Message, Mission, Stats, Submission, Task};
use crate::requests::{CreateMission, SubmitDeliverable};
use crate::a2a::ListTasksParams;

/// Builder for the blocking [`Client`]. Mirrors
/// [`crate::ClientBuilder`] and owns the same options.
#[derive(Debug, Clone, Default)]
pub struct ClientBuilder {
    inner: AsyncBuilder,
}

impl ClientBuilder {
    /// See [`crate::ClientBuilder::base_url`].
    #[must_use]
    pub fn base_url(mut self, url: impl Into<String>) -> Self {
        self.inner = self.inner.base_url(url);
        self
    }

    /// See [`crate::ClientBuilder::timeout`].
    #[must_use]
    pub fn timeout(mut self, timeout: Duration) -> Self {
        self.inner = self.inner.timeout(timeout);
        self
    }

    /// See [`crate::ClientBuilder::user_agent`].
    #[must_use]
    pub fn user_agent(mut self, ua: impl Into<String>) -> Self {
        self.inner = self.inner.user_agent(ua);
        self
    }

    /// See [`crate::ClientBuilder::api_key`].
    #[must_use]
    pub fn api_key(mut self, key: impl Into<String>) -> Self {
        self.inner = self.inner.api_key(key);
        self
    }

    /// Builds the blocking client, spinning up a private current-thread runtime.
    ///
    /// # Errors
    /// As [`crate::ClientBuilder::build`], plus [`Error::InvalidConfig`] if the
    /// Tokio runtime cannot be created.
    pub fn build(self) -> Result<Client> {
        // A current-thread runtime is sufficient (and lighter) for driving
        // one-shot blocking calls; it needs only `tokio/rt`, not the
        // multi-thread pool, keeping the `blocking` feature's dep surface small.
        let runtime = RuntimeBuilder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| Error::InvalidConfig(format!("failed to start runtime: {e}")))?;
        let inner = self.inner.build()?;
        Ok(Client { inner, runtime })
    }
}

/// Synchronous OABP client. See the [module docs](self).
#[derive(Debug)]
pub struct Client {
    inner: AsyncClient,
    runtime: Runtime,
}

impl Client {
    /// Starts a builder.
    #[must_use]
    pub fn builder() -> ClientBuilder {
        ClientBuilder::default()
    }

    /// Builds a blocking client with all defaults.
    ///
    /// # Errors
    /// As [`ClientBuilder::build`].
    pub fn new() -> Result<Self> {
        ClientBuilder::default().build()
    }

    /// The effective base URL (always ends in `/`).
    #[must_use]
    pub fn base_url(&self) -> &str {
        self.inner.base_url()
    }

    /// Blocking [`crate::Client::list_missions`].
    ///
    /// # Errors
    /// As the async equivalent.
    pub fn list_missions(&self) -> Result<Vec<Mission>> {
        self.runtime.block_on(self.inner.list_missions())
    }

    /// Blocking [`crate::Client::get_mission`].
    ///
    /// # Errors
    /// As the async equivalent.
    pub fn get_mission(&self, id: &str) -> Result<Mission> {
        self.runtime.block_on(self.inner.get_mission(id))
    }

    /// Blocking [`crate::Client::create_mission`].
    ///
    /// # Errors
    /// As the async equivalent.
    pub fn create_mission(&self, body: &CreateMission) -> Result<Mission> {
        self.runtime.block_on(self.inner.create_mission(body))
    }

    /// Blocking [`crate::Client::submit`].
    ///
    /// # Errors
    /// As the async equivalent.
    pub fn submit(&self, mission_id: &str, body: &SubmitDeliverable) -> Result<Submission> {
        self.runtime.block_on(self.inner.submit(mission_id, body))
    }

    /// Blocking [`crate::Client::stats`].
    ///
    /// # Errors
    /// As the async equivalent.
    pub fn stats(&self) -> Result<Stats> {
        self.runtime.block_on(self.inner.stats())
    }

    /// Blocking A2A `message/send`.
    ///
    /// # Errors
    /// As the async equivalent.
    pub fn a2a_send_message(&self, message: Message) -> Result<Task> {
        self.runtime.block_on(self.inner.a2a().send_message(message))
    }

    /// Blocking A2A `tasks/get`.
    ///
    /// # Errors
    /// As the async equivalent.
    pub fn a2a_get_task(&self, id: impl Into<String>) -> Result<Task> {
        self.runtime.block_on(self.inner.a2a().get_task(id))
    }

    /// Blocking A2A `tasks/list`.
    ///
    /// # Errors
    /// As the async equivalent.
    pub fn a2a_list_tasks(&self, params: ListTasksParams) -> Result<Vec<Task>> {
        self.runtime.block_on(self.inner.a2a().list_tasks(params))
    }
}
