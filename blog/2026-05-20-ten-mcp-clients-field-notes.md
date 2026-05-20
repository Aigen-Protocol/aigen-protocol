# Ten autonomous MCP clients, ten architectures: field notes from a public server

**Published:** 2026-05-20 | **Author:** AIGEN Protocol team | **Reading time:** ~8 min

---

We shipped a public MCP server on 13 May 2026. We did not announce it on any social network. We posted no "here's my new thing" tweet. We submitted to exactly zero MCP registries during the first week.

Within 7 days, ten autonomous clients with distinct architectures had connected.

This post is a technical log of what they did — specifically what broke, what succeeded, and what each failure mode tells a server implementer about the gap between the MCP spec and the reality of autonomous client behavior in the wild.

---

## Why this matters for server implementers

The official MCP spec describes a clean handshake: `initialize` → `notifications/initialized` → `tools/list` → use tools. What the spec does not tell you is how the actual client population navigates the gap between step 1 and step 2 when something goes wrong.

Our server received no intentional traffic. Every client found us through crawler indexing, directory submissions, or referrer chains we didn't orchestrate. That makes the dataset genuinely unbiased — these are the behaviors you will encounter if you ship a public MCP endpoint today.

---

## The ten architectures

### 1. REST-only (no MCP at all)

**Client:** `smolagents-oabp-example/1.0` | **Origin:** Hetzner Helsinki

The first autonomous framework-named client to appear fetched only REST endpoints (`/missions/active`, `/missions/{id}`) and never touched `/mcp`. It completed its work — polling for tasks, submitting a result — without a single MCP call.

**What this means for you:** Your REST surface must work independently of MCP. An implementation that requires agents to go through `/mcp` to reach any core functionality will be invisible to a significant fraction of the autonomous agent population. smolagents (Hugging Face's minimal framework) wraps tools as plain Python HTTP calls. It has no MCP client built in. It is not unusual.

---

### 2. Spec-conformant Streamable HTTP (clean success)

**Client:** `Ae/JS 0.62.0` | **Origin:** Cloudflare-routed

Sequence: `POST /mcp → 200 1182B` (init) → one transient `400` on a malformed retry → `POST /mcp → 200 41558B` (full tools/list, all 22 tools). Carries `Mcp-Session-Id` correctly. Returned for new sessions at 09:23Z, 09:26Z, 09:37Z throughout the day.

**What this means for you:** The spec is implementable and the success path exists. Ae/JS is the clearest positive trace in the dataset. If your server works for Ae/JS, the protocol is behaving.

---

### 3. Retry-resilient Node.js (self-corrects from 400)

**Client:** `node` (no version string) | **Origin:** Asia-Pacific

Three complete sessions in 37 minutes. Canonical sequence: `POST /mcp → 400` → `GET /mcp → 400` (probes wrong verb) → `POST /mcp → 200` (init) → `POST /mcp → 202` (notifications/initialized) → `POST /mcp → 200 41558B` (tools).

This client reads 400 bodies and adapts. It does not give up on the first failure.

**What this means for you:** Your `400` response bodies matter. Return `{"error": "use POST with Content-Type: application/json"}` rather than a generic nginx 400. A client that does error-recovery will read it and self-correct. Rate-limiting on error count will break this client — those initial `400` probes are *normal* exploration, not a broken request.

---

### 4. Stale-session SSE client (transport mismatch)

**Client:** `python-httpx/0.28.1` | **Origin:** Azure US

Sent `POST /messages/?session_id=63ff0fe3eb48497bb84e6cdcce240b6b → 202` (three times simultaneously) before establishing an SSE stream. The session_id was from a prior expired connection.

**What this means for you:** SSE and Streamable HTTP have separate lifecycle contracts. On SSE, the session_id travels as a URL parameter — the client must `GET /mcp/sse` first to receive a fresh id. A client that tries to reuse a prior session_id on SSE will successfully POST messages into the void (your server 202s them) but never gets a tool list. If you support both transports, document both in your `agent-card.json` separately. A correct `agent-card.json` for Streamable HTTP does not save an SSE client.

---

### 5. Teardown-first (DELETE after tools/list)

**Client:** `python-httpx/0.28.1` | **Origin:** Azure US (different IP from #4)

Cleanest lifecycle observed: init → `notifications/initialized` → tools/list → `DELETE /mcp → 200` → `GET /mcp → 200 5B` (health probe after teardown).

Same library as #4, different deployment, different transport choice. The transport choice is a deployment config, not a library constraint.

**What this means for you:** `DELETE {mcp_base}` MUST return `200`, not `404` or `405`. If your implementation doesn't track session state, return `200 0B` as a no-op. A `405 Method Not Allowed` breaks well-behaved clients that implement teardown per spec. Also: `GET {mcp_base}` with no active session must return `200`, not `404`. Clients use it as a liveness probe after teardown. A `404` reads as "endpoint gone."

---

### 6. Path-discovery loop with HTTP→HTTPS degradation (fails at step 2)

**Client:** `MCP-Client/1.0` | **Origin:** US VPS

The only client that explicitly named itself for MCP. Runs systematic path discovery: probes `/mcp`, `/api/mcp`, `/sse`, `/message`, `/v1/mcp`, `/` in sequence. Core failure: starts on HTTP, receives a `301 Permanent Redirect`, converts `POST` to `GET` on the redirect target. RFC 7231 §6.4.2 recommends but does not mandate preserving the method on 301. This client doesn't.

Achieves `POST /mcp → 200 1182B` on HTTPS, but the next call fails — `Mcp-Session-Id` not echoed. Client reads the homepage looking for discovery hints, then restarts the entire loop from HTTP.

**What this means for you:** Use `308 Permanent Redirect` (RFC 7538) instead of `301` for HTTPS upgrades on POST endpoints. `308` mandates method preservation. `301` does not. This is a one-line nginx change: `return 308 https://$host$request_uri;`. Two of our ten clients failed at exactly this point.

---

### 7. Session pre-flight probe (test-then-commit)

**Client:** `python-httpx/0.28.1` | **Origin:** AWS us-west-2

Phase A: init → immediate `DELETE /mcp → 200` (no tool calls, just testing the door). One second later: fresh init → `notifications/initialized` → full tools/list → DELETE → GET liveness probe. Then switches to SSE transport for actual work.

**What this means for you:** Accept `DELETE` immediately after `initialize` with no intermediate calls. The client is doing a connectivity pre-flight, not misbehaving. Don't interpret "init + no tool calls + DELETE" as an abandoned session and penalise the IP. Also: a single engagement window may use both transports back-to-back; session state must be isolated per-transport.

---

### 8. Path-blocked client (Content-Type missing)

**Client:** Unknown | **Origin:** US cloud (static IP, 3-day persistence)

Tried to connect for 72 hours. Every attempt returned `400`. Root cause: missing `Content-Type: application/json` header. Our server's strict content-type validation was correct per spec, but this client clearly expected lenient handling.

**What this means for you:** Accept `application/json` *and* `application/json; charset=utf-8` and bare-body POSTs from clearly structured JSON. A lenient `Content-Type` fallback recovers this class of client; the strict version just keeps failing forever. This is the most common silent failure in the dataset — a client that persists for 3 days without knowing why it's blocked.

---

### 9. OAuth-discovery-first, dual-transport (succeeds on both paths)

**Client:** Firefox 149.0 UA (developer tooling) | **Origin:** US

Before connecting: three consecutive RFC 9728 probes:
- `GET /.well-known/oauth-protected-resource/mcp/sse → 404`
- `GET /.well-known/oauth-protected-resource/mcp → 404`  
- `GET /.well-known/oauth-protected-resource → 404`

Falls back immediately. Then runs independent sessions on BOTH `/mcp` (Streamable HTTP) and `/mcp/sse`, calling tools on each. Re-checks OAuth metadata mid-handshake (between `initialize` and `notifications/initialized`).

**What this means for you:** Serve `/.well-known/oauth-protected-resource`. Content: `{"resource": "https://yourhost/mcp", "authorization_servers": [], "bearer_methods_supported": [], "scopes_supported": []}`. The `404` worked for this client because it has good fallback logic. Strict clients may refuse to connect without an explicit OAuth declaration. One nginx location covering `^/.well-known/oauth-protected-resource` handles all three path variants. This is now normative in AIP-1 §9.1.

---

### 10. Parallel session fanout (Cloudflare Workers fleet)

**Client:** No UA | **Origin:** Cloudflare edge (172.68.x.x / 172.69.x.x range)

Two distinct Cloudflare IPs polling every ~60-90 minutes. In the last observed window: two sessions opened at the *same second* — both receiving init (`1182B`) and tools/list (`41558B`) simultaneously. This is not a retry; it is concurrent session creation from parallel worker instances.

**What this means for you:** Session state cannot be tied to a process or thread. If two init calls arrive simultaneously from the same logical client (behind edge routing, different IPs, same second), your server must issue independent session IDs to each and handle them in isolation. A stateful singleton session model breaks this client silently — they both succeed init but one or both may get stale state on follow-up calls.

---

## The one pattern that summarises all ten

The step-2 problem.

Every client in this dataset navigated `initialize → 200` correctly. The failures happened on the *second* call — the `notifications/initialized` POST, or the first `tools/list`, or the first real tool call. In 6 of 10 architectures, that second call was where something broke.

The causes: wrong method on redirect (308 vs 301), missing session header echo, wrong transport lifecycle, stale session ID, concurrent state collision.

The spec describes the handshake well. What it doesn't describe is what the server should do when the client skips `notifications/initialized`, or sends it twice, or arrives with a stale session ID from 3 days ago, or opens 4 parallel sessions at once. These are the failure modes that actually occur.

We've proposed a normative extension to AIP-1 §7 to address the lifecycle contract gaps we observed. Discussion: [github.com/Aigen-Protocol/aigen-protocol/issues/25](https://github.com/Aigen-Protocol/aigen-protocol/issues/25).

---

## TL;DR for server implementers

| Mitigation | Impact |
|---|---|
| Use `308` instead of `301` for HTTPS upgrades | Fixes arch #6 + any similar client |
| Return `200` on `DELETE /mcp` (no-op if stateless) | Required by arch #5, #7 |
| Return `200` on `GET /mcp` with no active session | Required by arch #5, #7, #9 |
| Accept Content-Type-less JSON POSTs | Unblocks arch #8 |
| Serve `/.well-known/oauth-protected-resource` | Removes ambiguity for arch #9 |
| Return descriptive JSON on `400`, not bare HTTP error | Enables self-correction in arch #3 |
| Keep REST surface independent of MCP | Required for arch #1 |
| Isolate session state per-transport | Required for arch #4 vs #7 |
| Handle concurrent parallel init calls | Required for arch #10 |
| Don't rate-limit on initial `400` probes | Protects arch #3, #8 |

---

The dataset is live. SECOND_IMPLEMENTATION.md in the AIGEN repo is updated after each new architecture is observed: [github.com/Aigen-Protocol/aigen-protocol](https://github.com/Aigen-Protocol/aigen-protocol)

We opened a discussion on the official MCP spec repo about the lifecycle contract gaps observed here: [github.com/modelcontextprotocol/modelcontextprotocol/issues/2755](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/2755)
