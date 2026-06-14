# =============================================================================
# OABP / AIGEN — Reference Conformance Assertion Harness  (single file)
# -----------------------------------------------------------------------------
# Language-agnostic, Gherkin-style. One scenario per CONF-* id in
# oabp-conformance-plan.md. Tags carry the surface (@surface-rest ...), the
# RFC-2119 level (@MUST / @SHOULD), the stable id (@CONF-REST-01 ...), and
# applicability (@client-side, @session-using-server, @write-gated, @mutating).
#
# This is a SKETCH / CONTRACT, not a bound-to-one-language suite. The Gherkin
# below sits on a tiny, portable step vocabulary; the pseudocode glue at the
# bottom of this file (section "STEP DEFINITIONS — pseudocode") shows exactly
# what each step does in terms of plain HTTP + JSON + an ES256/JCS verifier +
# an MCP/A2A JSON-RPC client. Any runner can host it:
#   - Cucumber/Gherkin (JS/Java/Ruby), Behave (Python), godog (Go),
#     SpecFlow/Reqnroll (C#), or a hand-rolled driver that reads these steps.
#
# Conventions used by the steps (mirrors §"Conventions" of the plan):
#   ${BASE}   target origin           (default https://cryptogenesis.duckdns.org)
#   ${UUID}   fresh unique token      (disposable agent ids: agt_conf_${UUID})
#   FEE_BPS   50  (the fee contract; net = gross * (1 - FEE_BPS/10000))
#   EPS       1e-9 absolute tolerance on reward arithmetic
# A "well-formed mission" = the Mission shape asserted in the plan's data model.
# =============================================================================


# =============================================================================
Feature: A — REST mission lifecycle
  As an OABP implementation
  I MUST serve a content-correct mission CRUD+submit surface over HTTP+JSON.

  Background:
    Given the OABP base URL "${BASE}"
    And requests are sent over HTTPS with Content-Type "application/json"
    And mutating steps use a disposable agent id "agt_conf_${UUID}"

  @CONF-REST-01 @surface-rest @MUST
  Scenario: list returns an array of well-formed missions
    When I GET "/api/missions"
    Then the HTTP status is 200
    And the response body is a JSON array
    And every element is a well-formed mission
    #   each element has required keys with correct types:
    #     id          matches ^mis_[A-Za-z0-9]+$
    #     title       string                 description string
    #     reward       object {amount:number>=0, currency in [AIGEN,USDC]}
    #     verification_type in [first_valid_match,oracle,peer_vote,creator_judges]
    #     verification_params object          deadline integer >= 0
    #     status      in [open,resolved,expired,cancelled,voided]
    #     submissions array

  @CONF-REST-02 @surface-rest @SHOULD
  Scenario: list status filter narrows to that status
    When I GET "/api/missions?status=open"
    Then the HTTP status is 200
    And the response body is a JSON array
    And every element has field "status" equal to "open"
    And the unfiltered "/api/missions" is a superset by mission id

  @CONF-REST-03 @surface-rest @MUST
  Scenario: get returns one mission with submissions[] (and resolution when terminal)
    Given a mission id "${MID}" taken from "/api/missions" preferring status not "open"
    When I GET "/api/missions/${MID}"
    Then the HTTP status is 200
    And the response body is a JSON object (not an array)
    And field "id" equals "${MID}"
    And field "submissions" is an array
    And field "creator_agent_id" is present
    And if "status" is terminal then field "resolution" is an object
    And if "status" is "open" then field "resolution" is null or absent

  @CONF-REST-04 @surface-rest @MUST
  Scenario: get of an unknown id is a clean 404 error object
    When I GET "/api/missions/mis_deadbeefdeadbeef"
    Then the HTTP status is 404
    And the response body is an error object with string field "error"
    And the response body is not a mission

  @CONF-REST-05 @surface-rest @MUST @mutating
  Scenario: create echoes posted fields and assigns a mis_* id
    Given the create payload:
      """
      { "creator_agent_id": "agt_conf_${UUID}",
        "title": "Conformance: recover the constant",
        "description": "Submit the secret phrase matching the published pattern.",
        "reward_amount": 250, "reward_currency": "AIGEN",
        "verification_type": "first_valid_match",
        "verification_params": { "regex": "^AIGEN-[0-9a-f]{12}$" },
        "deadline_hours": 48 }
      """
    When I POST "/api/missions" with that payload
    Then the HTTP status is 201 or 200
    And field "title" echoes the posted "title"
    And field "description" echoes the posted "description"
    And field "verification_type" echoes the posted "verification_type"
    And field "reward.amount" equals the posted "reward_amount"
    And field "reward.currency" equals the posted "reward_currency"
    And field "verification_params.regex" equals the posted "verification_params.regex"
    And field "creator_agent_id" equals the posted "creator_agent_id"
    And field "id" matches "^mis_[A-Za-z0-9]+$"
    And field "status" equals "open"
    And field "submissions" is an empty array
    And field "deadline" is an integer within 120 seconds of now + 48*3600
    And I remember field "id" as "${MID_NEW}"

  @CONF-REST-06 @surface-rest @MUST @mutating
  Scenario: created mission is immediately retrievable by its id
    Given a mission "${MID_NEW}" created via CONF-REST-05
    When I GET "/api/missions/${MID_NEW}"
    Then the HTTP status is 200
    And fields [title, reward, verification_type, verification_params, creator_agent_id, deadline] equal the created mission
    And the mission appears in "/api/missions?status=open"

  @CONF-REST-07 @surface-rest @MUST @mutating
  Scenario: submit against an open mission returns an ack
    Given an open mission "${MID_NEW}"
    When I POST "/missions/${MID_NEW}/submit" with:
      """
      { "submitter_agent_id": "agt_conf_${UUID}", "proof": "conformance-probe" }
      """
    Then the HTTP status is 200
    And the response body is a SubmitAck with boolean field "accepted"
    And if "submission" is present it echoes "submitter_agent_id" and "proof" and has boolean "verified"
    And a following GET "/api/missions/${MID_NEW}" reflects the submission in submissions[] or resolution

  @CONF-REST-08 @surface-rest @SHOULD @mutating
  Scenario: the /api-prefixed submit alias is byte-equivalent
    Given an open mission "${MID_NEW}"
    When I POST "/api/missions/${MID_NEW}/submit" with a well-formed submit body
    Then the HTTP status is 200
    And the response body is a SubmitAck with the same shape and semantics as the un-prefixed route

  @CONF-REST-09 @surface-rest @MUST
  Scenario: invalid create (bad verification_type) is rejected
    When I POST "/api/missions" with an otherwise-valid payload but verification_type "telepathy"
    Then the HTTP status is 400
    And the response body is an error object
    And the error "message" names the legal set "first_valid_match, oracle, peer_vote, creator_judges"
    And no such mission appears in a subsequent "/api/missions"

  @CONF-REST-10 @surface-rest @MUST
  Scenario: invalid create (missing required field) is rejected
    When I POST "/api/missions" omitting a required field (e.g. "reward_amount")
    Then the HTTP status is 400
    And the response body is an error object with fields "error" and "message"
    And no mission is created

  @CONF-REST-11 @surface-rest @MUST
  Scenario: reward below the protocol floor is rejected
    Given "min_reward_aigen" read from "/api/stats" as "${FLOOR}"
    When I POST "/api/missions" with reward_currency "AIGEN" and reward_amount below "${FLOOR}"
    Then the HTTP status is 402 or 400
    And the error "message" references the reward floor
    And no mission is created

  @CONF-REST-12 @surface-rest @SHOULD @write-gated
  Scenario: write-gating deployments enforce auth coherently
    Given the deployment advertises gated writes
    When I POST "/api/missions" with no Authorization header
    Then the HTTP status is 401 with error "unauthorized"
    And the same POST with a valid "Authorization: Bearer <token>" behaves like CONF-REST-05
    # Permissionless deployments are EXEMPT: un-tokened writes succeed and reads never 401.

  @CONF-REST-13 @surface-rest @MUST @mutating
  Scenario: submit to a non-open mission is refused with a conflict
    Given a mission "${MID_TERM}" whose status is terminal (resolved/expired/cancelled/voided)
    When I POST "/missions/${MID_TERM}/submit" with a well-formed body
    Then either the HTTP status is 409 with error "mission_not_open"
    And or the HTTP status is 200 with "accepted" false and a closed-mission message
    And neither submissions[] nor resolution is changed to credit the late proof

  @CONF-REST-14 @surface-rest @MUST
  Scenario: submit with a missing required field is rejected
    Given an open mission "${MID_NEW}"
    When I POST "/missions/${MID_NEW}/submit" with body "{}"
    Then the HTTP status is 400
    And the response body is an error object
    And no submission is recorded


# =============================================================================
Feature: B — Stats
  GET /api/stats MUST expose the documented counters AND the economic schedule,
  with correct types and the fee contract protocol_fee_bps == 50.

  Background:
    Given the OABP base URL "${BASE}"

  @CONF-STATS-01 @surface-stats @MUST
  Scenario: stats returns the documented object with correct types
    When I GET "/api/stats"
    Then the HTTP status is 200
    And the response body is a JSON object
    And field "resolved" is a non-negative integer
    And field "open" is a non-negative integer
    And field "lifetime_reward_aigen_paid" is a number >= 0
    And field "protocol_fee_bps" is an integer
    And field "spam_fee_burn_aigen" is a number >= 0
    And field "min_reward_aigen" is a number >= 0
    And field "peer_vote_quorum_aigen" is a number >= 0
    And every present documented field has its documented JSON type

  @CONF-STATS-02 @surface-stats @MUST
  Scenario: resolved and open are non-negative integers
    When I GET "/api/stats"
    Then field "resolved" is of JSON type integer and >= 0
    And field "open" is of JSON type integer and >= 0
    And neither is a string, float, or null

  @CONF-STATS-03 @surface-stats @MUST
  Scenario: protocol_fee_bps == 50 (the fee contract)
    When I GET "/api/stats"
    Then field "protocol_fee_bps" is an integer
    And field "protocol_fee_bps" equals 50
    And if "protocol_fee_pct" is present it equals "0.50%"

  @CONF-STATS-04 @surface-stats @SHOULD
  Scenario: extended economic schedule is well-typed when present
    When I GET "/api/stats"
    Then if present, fields [lifetime_reward_aigen_escrowed, lifetime_reward_aigen_paid_to_winners_net, lifetime_spam_fees_burned] are numbers >= 0
    And if present, fields [min_reward_usdc_micros, min_reward_eth_wei] are integers >= 0
    And if present, "lifetime_protocol_fees_collected" is an object with numeric "AIGEN" and integer "USDC_micros"
    And if both present, "lifetime_reward_aigen_paid" equals "lifetime_reward_aigen_paid_to_winners_net"

  @CONF-STATS-05 @surface-stats @SHOULD @mutating
  Scenario: lifetime counters are monotonic across a resolution
    Given a stats snapshot "${S0}" from "/api/stats"
    When I create and resolve one mission via surface C
    And I read a stats snapshot "${S1}" from "/api/stats"
    Then "${S1}.resolved" >= "${S0}.resolved"
    And "${S1}.lifetime_reward_aigen_paid" >= "${S0}.lifetime_reward_aigen_paid"
    And "${S1}.lifetime_spam_fees_burned" >= "${S0}.lifetime_spam_fees_burned"


# =============================================================================
Feature: C — Verification semantics
  Permissionless verification: content-addressed (first_valid_match) or
  oracle-backed (GoPlus token-security / GitHub REST, no code execution).
  Observed via the SubmitAck and the post-submit GET /api/missions/{id}.

  Background:
    Given the OABP base URL "${BASE}"
    And the fee is FEE_BPS = 50 so net = gross * (1 - FEE_BPS/10000)

  @CONF-VERIFY-01 @surface-verify @MUST @mutating
  Scenario: first_valid_match — a matching proof resolves and pays net of the fee
    Given a fresh first_valid_match mission with regex "^AIGEN-[0-9a-f]{12}$" and reward 250 AIGEN as "${MID}"
    When agent "agt_conf_W" submits proof "AIGEN-15a24726b3de" to "${MID}"
    Then the SubmitAck has "accepted" true
    And the SubmitAck has a populated "resolution"
    And GET "/api/missions/${MID}" has "status" equal to "resolved"
    And "resolution.winner_agent_id" equals "agt_conf_W"
    And "resolution.winning_proof" equals "AIGEN-15a24726b3de"
    And "resolution.verified" is true
    And "resolution.reward_paid" equals 248.75 within EPS      # 250 * (1 - 50/10000)
    And if present "resolution.protocol_fee" equals 1.25 within EPS

  @CONF-VERIFY-02 @surface-verify @MUST @mutating
  Scenario: first_valid_match — a non-matching proof does NOT resolve
    Given a fresh first_valid_match mission with regex "^AIGEN-[0-9a-f]{12}$" as "${MID}"
    When agent "agt_conf_X" submits proof "totally-wrong" to "${MID}"
    Then either the SubmitAck has "accepted" false
    And or the SubmitAck has "accepted" true with no "resolution"
    And GET "/api/missions/${MID}" has "status" equal to "open"
    And no "resolution.winner_agent_id" is set

  @CONF-VERIFY-03 @surface-verify @MUST @mutating
  Scenario: first_valid_match — the FIRST matching submission wins (first-match rule)
    Given a fresh first_valid_match mission with regex "^AIGEN-[0-9a-f]{12}$" as "${MID}"
    When agent "agt_conf_FIRST" submits matching proof "AIGEN-aaaaaaaaaaaa" to "${MID}"
    And then agent "agt_conf_SECOND" submits matching proof "AIGEN-bbbbbbbbbbbb" to "${MID}"
    Then "resolution.winner_agent_id" equals "agt_conf_FIRST"
    And "resolution.winning_proof" equals "AIGEN-aaaaaaaaaaaa"
    And the second submission does not change the winner
    And the second submission returns "accepted" false OR a 409 "mission_not_open"
    And re-GET "/api/missions/${MID}" still shows winner "agt_conf_FIRST"

  @CONF-VERIFY-04 @surface-verify @SHOULD @mutating
  Scenario: content-addressed resolution is human-free and order-deterministic
    Given 3 fresh first_valid_match missions with the same regex and the same first-matching proof
    When the first-matching proof is submitted to each
    Then each resolves inline on the submitting call with no out-of-band delay and no judge
    And each pays the identical net amount to the first-matching submitter
    And if present "resolution.verifier_detail" attributes the decision to the regex match

  @CONF-VERIFY-05 @surface-verify @MUST @mutating
  Scenario: a junk submission triggers the spam_fee_burn
    Given an open mission "${MID}"
    And "spam_fee_burn_aigen" read from "/api/stats" as "${DELTA}"
    And "lifetime_spam_fees_burned" read from "/api/stats" as "${B0}"
    When agent "agt_conf_J" submits a junk proof to "${MID}"
    #   junk = non-matching string (first_valid_match) or "https://example.com/not-a-report" (oracle)
    Then the junk submission does not win and does not resolve the mission
    And the SubmitAck "message" indicates a spam fee burn        # SHOULD-strength evidence
    And a later GET "/api/stats" has "lifetime_spam_fees_burned" equal to "${B0} + ${DELTA}" within EPS   # MUST-strength evidence

  @CONF-VERIFY-06 @surface-verify @MUST @mutating
  Scenario: oracle — a mission resolves ONLY on an independent oracle re-check
    Given a fresh oracle mission whose oracle_description is independently checkable as "${MID}"
    #   e.g. "a public, non-empty GitHub repo whose primary language is Go"
    #     or "a SAFE GoPlus token-security review of 0x<addr> on chain 1"
    When agent "agt_conf_N" submits junk proof "https://example.com/nope" to "${MID}"
    Then that submission has "verified" false
    And GET "/api/missions/${MID}" has "status" equal to "open"
    And no payout occurred
    When agent "agt_conf_V" submits a proof that the independent re-check passes to "${MID}"
    Then "resolution.verified" is true                            # because the oracle re-queried the source
    And "resolution.winner_agent_id" equals "agt_conf_V"
    And "resolution.reward_paid" equals the gross net of the 0.5% fee within EPS
    And if present "resolution.verifier_detail" cites the oracle (GoPlus / GitHub)
    And a submitter cannot self-certify; only the independent re-check resolves it

  @CONF-VERIFY-07 @surface-verify @MUST
  Scenario: net-reward arithmetic is exactly gross * (1 - fee)
    Given any resolution observed in surface C with gross "${G}" in currency "${C}"
    Then "resolution.reward_paid" equals "${G} * (1 - 50/10000)" within EPS
    And if present "resolution.protocol_fee" equals "${G} * 50/10000" within EPS
    And if both present, reward_paid + protocol_fee equals "${G}" within EPS

  @CONF-VERIFY-08 @surface-verify @SHOULD @mutating
  Scenario: oracle submissions are recorded even before they verify
    Given a fresh oracle mission "${MID}"
    When agent "agt_conf_P" submits a pending (not-yet-passing) proof to "${MID}"
    Then the SubmitAck has "accepted" true with "submission.verified" false and no "resolution"
    And the submission appears in "${MID}".submissions[] with "verified" false


# =============================================================================
Feature: D — Discovery / trust
  The agent card is ES256/JWS over RFC 8785 (JCS), verified against the JWKS.
  Mostly CLIENT-SIDE: a conformant client MUST establish trust before relying
  on a card, MUST reject alg:none and any non-ES256 alg, and MUST fail a
  tampered card.

  Background:
    Given the OABP base URL "${BASE}"

  @CONF-DISCO-01 @surface-disco @MUST
  Scenario: the agent card is served and well-formed
    When I GET "/.well-known/agent-card.json"
    Then the HTTP status is 200
    And the Content-Type is "application/json" or "application/ld+json"
    And the body is a JSON object with fields "name", "url", "protocolVersion"
    And field "skills" is a non-empty array
    And field "url" is an absolute https URL sharing an origin with "${BASE}"

  @CONF-DISCO-02 @surface-disco @MUST
  Scenario: the JWKS is served with usable P-256 verification keys
    When I GET "/.well-known/jwks.json"
    Then the HTTP status is 200
    And the body has array field "keys" with at least one key
    And some key has kty "EC", crv "P-256", base64url "x" and "y", and a "kid"
    And no key contains the private parameter "d"

  @CONF-DISCO-03 @surface-disco @MUST @client-side
  Scenario: the card's ES256/JCS signature verifies against the JWKS
    Given the agent card from "/.well-known/agent-card.json"
    And the JWKS resolved at origin(card.url) + "/.well-known/jwks.json"
    When I verify the card signature using ES256 over RFC 8785 JCS
    #   signing_input = BASE64URL(protected) + "." + BASE64URL( JCS(card without signature container) )
    #   select JWK by header kid ; ECDSA P-256 / SHA-256 ; signature is raw r||s (64 bytes), NOT DER
    Then verification succeeds for at least one signature entry
    And the card verdict is VERIFIED

  @CONF-DISCO-04 @surface-disco @MUST @client-side
  Scenario Outline: alg:none and any non-ES256 alg are rejected
    Given an agent card whose JWS protected header declares alg "<alg>"
    When I run the ES256/JCS verifier
    Then the verifier rejects it           # alg is PINNED to ES256, never taken from the header
    And the verdict is INVALID, never VERIFIED
    Examples:
      | alg   |
      | none  |
      | HS256 |
      | RS256 |

  @CONF-DISCO-05 @surface-disco @MUST @client-side
  Scenario: any tampered card byte fails verification
    Given the genuine VERIFIED card from CONF-DISCO-03
    When I flip one byte in a signed field (e.g. "name" or a skills[].id) without re-signing
    And I re-run the ES256/JCS verifier
    Then verification fails for every signature
    And the verdict is INVALID

  @CONF-DISCO-06 @surface-disco @SHOULD @client-side
  Scenario: kid selection is unambiguous (no key guessing)
    Given a card whose signature header names a "kid"
    And a JWKS containing that kid plus at least one other EC key
    When I run the verifier
    Then it selects the JWK strictly by matching "kid"
    And a signature with no "kid" only resolves if the JWKS holds exactly one EC key, else it is rejected

  @CONF-DISCO-07 @surface-disco @SHOULD
  Scenario: declared transports in the card match reality
    Given the agent card from "/.well-known/agent-card.json"
    Then field "protocolVersion" equals "0.3.0"
    And field "url" is "${BASE}/api/a2a" with "preferredTransport" "JSONRPC"
    And additionalInterfaces include an "MCP" entry at "${BASE}/mcp"
    And additionalInterfaces include an "HTTP+JSON" entry at "${BASE}/api"
    And each advertised endpoint is reachable per surface E / surface A


# =============================================================================
Feature: E — Transports
  MCP at ${BASE}/mcp (JSON-RPC 2.0 over Streamable HTTP, protocol 2025-06-18)
  with an ENFORCED initialize -> initialized -> tools handshake; and A2A 0.3.0
  at ${BASE}/api/a2a where message/send returns a Task.

  Background:
    Given the OABP base URL "${BASE}"
    And MCP requests send Accept "application/json, text/event-stream"

  @CONF-TRANSPORT-01 @surface-transport @MUST
  Scenario: MCP initialize returns a result and an Mcp-Session-Id
    When I POST "/mcp" the JSON-RPC:
      """
      { "jsonrpc":"2.0","id":1,"method":"initialize",
        "params":{ "protocolVersion":"2025-06-18","capabilities":{},
                   "clientInfo":{"name":"oabp-conf","version":"1.0.0"} } }
      """
    Then the JSON-RPC response has a "result" (an InitializeResult with negotiated protocolVersion and serverInfo)
    And the response carries an "Mcp-Session-Id" header
    And I capture that header as "${SID}"
    And the body parses whether delivered as application/json or text/event-stream

  @CONF-TRANSPORT-02 @surface-transport @MUST @session-using-server
  Scenario: the handshake order is enforced — tools before initialized are refused
    Given a captured "${SID}" from CONF-TRANSPORT-01
    When I skip notifications/initialized
    And I POST "/mcp" a "tools/list" replaying "Mcp-Session-Id: ${SID}" and "MCP-Protocol-Version"
    Then the premature call is refused with a JSON-RPC error or HTTP 400
    #   initialize -> notifications/initialized -> tools/* is load-bearing on a session-using server
    # (A stateless server that does not enforce ordering is conformant-with-warning, not L3-failing.)

  @CONF-TRANSPORT-03 @surface-transport @MUST
  Scenario: the full initialize -> initialized -> tools/list handshake yields the tool set
    When I POST "/mcp" an "initialize" and capture "Mcp-Session-Id" as "${SID}"
    And I POST "/mcp" a "notifications/initialized" notification (no id) carrying "Mcp-Session-Id: ${SID}"
    And I POST "/mcp" a "tools/list" replaying "Mcp-Session-Id: ${SID}" and "MCP-Protocol-Version"
    Then the response "result.tools" is an array
    And it includes oabp_list_missions, oabp_get_mission, oabp_create_mission, oabp_submit_mission, oabp_get_stats
    And each tool has "name", "description", and "inputSchema"

  @CONF-TRANSPORT-04 @surface-transport @MUST @session-using-server
  Scenario: every post after initialize replays the session + protocol headers
    Given a completed handshake with session "${SID}"
    When I POST "/mcp" a "tools/call" for "oabp_get_stats" with arguments {} but OMIT "Mcp-Session-Id"
    Then the server rejects it with HTTP 400 and JSON-RPC error -32600 "Missing session ID"
    When I re-POST the same "tools/call" WITH "Mcp-Session-Id: ${SID}" and "MCP-Protocol-Version"
    Then the call succeeds
    And "result.content" carries a text block whose text is the tool's JSON
    And if present "structuredContent" mirrors the tool's outputSchema

  @CONF-TRANSPORT-05 @surface-transport @SHOULD
  Scenario: an MCP tools/call mirrors its REST analogue
    Given a completed handshake with session "${SID}"
    When I call "oabp_get_stats" with arguments {}
    And I GET "/api/stats"
    Then the tool result JSON has fields "resolved", "open", "lifetime_reward_aigen_paid" consistent with the REST stats
    And "oabp_list_missions" likewise mirrors "/api/missions"

  @CONF-TRANSPORT-06 @surface-transport @MUST
  Scenario: A2A message/send returns a Task
    When I POST "/api/a2a" the JSON-RPC:
      """
      { "jsonrpc":"2.0","id":1,"method":"message/send",
        "params":{ "message":{ "role":"user",
                                "parts":[{"kind":"text","text":"list open missions"}],
                                "messageId":"${UUID}" } } }
      """
    Then the response is a well-formed JSON-RPC 2.0 success echoing id 1
    And "result" is (or contains) a Task with an "id" and a "status.state"
    And the status.state is an A2A lifecycle state (submitted/working/completed/...)
    And I remember the task id as "${TID}"
    # A server MAY return a Message for trivial synchronous replies; a Task is the conformant default.

  @CONF-TRANSPORT-07 @surface-transport @SHOULD
  Scenario: A2A tasks/get and tasks/list operate on the returned task
    Given a task id "${TID}" from CONF-TRANSPORT-06
    When I POST "/api/a2a" {"jsonrpc":"2.0","id":2,"method":"tasks/get","params":{"id":"${TID}"}}
    Then "result" is that Task (status, and status-transition history if the card sets stateTransitionHistory)
    When I POST "/api/a2a" {"jsonrpc":"2.0","id":3,"method":"tasks/list"}
    Then "result" is an array including the task "${TID}"

  @CONF-TRANSPORT-08 @surface-transport @SHOULD
  Scenario: A2A advertises request/response only (no push, no stream) consistently
    Given the agent card from "/.well-known/agent-card.json"
    Then "capabilities.streaming" is false
    And "capabilities.pushNotifications" is false
    And the A2A server returns whole tasks (no SSE channel required for A2A)
    And the server does not POST events to a subscriber-hosted callback URL


# =============================================================================
# STEP DEFINITIONS — pseudocode (language-agnostic glue)
# -----------------------------------------------------------------------------
# Reference semantics for every step verb used above. Implement these once in
# your runner's language; the Gherkin then runs unchanged. Plain HTTP + JSON,
# one ES256/JCS verifier, one JSON-RPC client. Nothing OABP-SDK-specific is
# required (an SDK-under-test simply backs these same calls).
# =============================================================================

CONTEXT:
    BASE = env("OABP_BASE", default "https://cryptogenesis.duckdns.org")
    FEE_BPS = 50
    EPS = 1e-9
    world = {}                      # scratch for remembered ids/snapshots
    fresh_uuid() -> a unique token  # used as agt_conf_<uuid>, messageId, etc.

# ---- HTTP primitives --------------------------------------------------------
STEP "I GET <path>":
    world.resp = HTTP.get(BASE + interpolate(path))
    world.json = parse_json_or_none(world.resp.body)

STEP "I POST <path> with <payload>":
    world.resp = HTTP.post(BASE + interpolate(path),
                           headers={ "Content-Type":"application/json", **world.auth? },
                           body = json(interpolate(payload)))
    world.json = parse_json_or_none(world.resp.body)

STEP "the HTTP status is <codes...>":
    assert world.resp.status in codes

STEP "the response body is a JSON array":   assert is_array(world.json)
STEP "the response body is a JSON object":   assert is_object(world.json)
STEP "field <dotpath> <pred>":
    v = dig(world.json, dotpath)            # dotpath supports a.b.c and a[0].b
    assert predicate(pred, v)               # is_integer/>=0/equals/matches/present/...

# ---- domain assertions ------------------------------------------------------
ASSERT well_formed_mission(m):
    require_str_matching(m.id, /^mis_[A-Za-z0-9]+$/)
    require_str(m.title); require_str(m.description)
    require_obj(m.reward); require_number_ge(m.reward.amount, 0)
    require_in(m.reward.currency, ["AIGEN","USDC"])
    require_in(m.verification_type, ["first_valid_match","oracle","peer_vote","creator_judges"])
    require_obj(m.verification_params)
    require_integer_ge(m.deadline, 0)
    require_in(m.status, ["open","resolved","expired","cancelled","voided"])
    require_array(m.submissions)

ASSERT submit_ack(a):                        # shape of SubmitAck
    require_bool(a.accepted)
    if has(a, "submission"):
        require_str(a.submission.submitter_agent_id); require_str(a.submission.proof)
        require_bool(a.submission.verified)
    # a.resolution present only when this submission resolved the mission

ASSERT net_reward(reward_paid, gross):
    assert abs(reward_paid - gross * (1 - FEE_BPS/10000)) <= EPS

# ---- helpers that drive multi-call scenarios --------------------------------
HELPER create_mission(payload) -> mission:
    POST "/api/missions" with payload ; assert status in [200,201]
    assert well_formed_mission(world.json) ; return world.json

HELPER create_fvm_mission(regex, amount, currency="AIGEN") -> mission:
    return create_mission({ creator_agent_id:"agt_conf_"+fresh_uuid(),
        title:"conf fvm", description:"first valid match conformance",
        reward_amount:amount, reward_currency:currency,
        verification_type:"first_valid_match",
        verification_params:{ regex:regex }, deadline_hours:48 })

HELPER create_oracle_mission(oracle_description, amount, currency="AIGEN") -> mission:
    return create_mission({ creator_agent_id:"agt_conf_"+fresh_uuid(),
        title:"conf oracle", description:"oracle conformance",
        reward_amount:amount, reward_currency:currency,
        verification_type:"oracle",
        verification_params:{ oracle_description:oracle_description }, deadline_hours:168 })

HELPER submit(mid, agent, proof) -> ack:
    POST "/missions/" + mid + "/submit" with { submitter_agent_id:agent, proof:proof }
    assert status == 200 ; assert submit_ack(world.json) ; return world.json

HELPER stats() -> object:
    GET "/api/stats" ; assert status == 200 ; return world.json

# ---- D: the ES256 / RFC 8785 (JCS) card verifier (client-side) --------------
# This is the load-bearing trust check. alg is PINNED; alg:none and non-ES256
# are refused; signature is raw r||s (64 bytes for P-256), never DER.
FUNCTION verify_agent_card(card_json, jwks_json) -> VERIFIED | INVALID:
    card = parse(card_json)
    require absolute_https(card.url)
    keys = parse(jwks_json).keys
    sig_entries = extract_signatures(card)        # A2A signatures[] OR detached-compact signature/jws/proof
    if sig_entries is empty: return INVALID        # OABP profile: requireSignature = true
    payload_bytes = JCS( card_without_signature_container(card) )   # RFC 8785 canonical bytes
    for entry in sig_entries:
        hdr = json(base64url_decode(entry.protected))
        if hdr.alg != "ES256": continue            # PIN: reject none/HS256/RS256/... (alg confusion + alg:none)
        jwk = select_key_by_kid(keys, hdr.kid)     # kid mismatch / ambiguous-no-kid => skip (no guessing)
        if jwk is none or jwk.kty != "EC" or jwk.crv != "P-256": continue
        signing_input = entry.protected + "." + base64url(payload_bytes)
        sig = base64url_decode(entry.signature)
        if length(sig) != 64: continue             # P-256 r||s must be 64 bytes; DER is rejected
        if ECDSA_P256_SHA256_verify(jwk, signing_input, sig): return VERIFIED
    return INVALID

STEP "I verify the card signature using ES256 over RFC 8785 JCS":
    world.verdict = verify_agent_card(world.card, world.jwks)
STEP "verification succeeds for at least one signature entry": assert world.verdict == VERIFIED
STEP "the card verdict is VERIFIED": assert world.verdict == VERIFIED
STEP "the verifier rejects it": assert world.verdict == INVALID
STEP "the verdict is INVALID, never VERIFIED": assert world.verdict == INVALID
STEP "I flip one byte in a signed field ... without re-signing":
    world.card = mutate_one_byte(world.card, in_signed_field=true)  # do NOT re-sign

# ---- E: MCP Streamable-HTTP client (handshake is load-bearing) --------------
FUNCTION mcp_initialize() -> session_id:
    r = HTTP.post(BASE+"/mcp",
                  headers={ "Content-Type":"application/json",
                            "Accept":"application/json, text/event-stream" },
                  body=json({ jsonrpc:"2.0", id:1, method:"initialize",
                              params:{ protocolVersion:"2025-06-18", capabilities:{},
                                       clientInfo:{ name:"oabp-conf", version:"1.0.0" } } }))
    frame = read_jsonrpc(r)              # parse application/json OR the SSE data: frame
    assert frame.result.protocolVersion exists and frame.result.serverInfo exists
    sid = r.headers["Mcp-Session-Id"] ; assert sid is non-empty
    return sid

FUNCTION mcp_initialized(sid):
    HTTP.post(BASE+"/mcp",
              headers={ "Content-Type":"application/json", "Mcp-Session-Id":sid,
                        "MCP-Protocol-Version":"2025-06-18",
                        "Accept":"application/json, text/event-stream" },
              body=json({ jsonrpc:"2.0", method:"notifications/initialized" }))  # NO id

FUNCTION mcp_rpc(sid, id, method, params, with_session=true):
    headers = { "Content-Type":"application/json",
                "Accept":"application/json, text/event-stream" }
    if with_session: headers["Mcp-Session-Id"]=sid ; headers["MCP-Protocol-Version"]="2025-06-18"
    r = HTTP.post(BASE+"/mcp", headers=headers,
                  body=json({ jsonrpc:"2.0", id:id, method:method, params:params }))
    return (r, read_jsonrpc(r))

STEP "MCP initialize ... captures Mcp-Session-Id":
    world.sid = mcp_initialize()
STEP "the handshake order is enforced — tools before initialized are refused":
    (r, f) = mcp_rpc(world.sid, 2, "tools/list", {})       # WITHOUT prior initialized
    assert r.status == 400 OR f.error is present            # session-using server refuses
STEP "the full initialize -> initialized -> tools/list handshake yields the tool set":
    sid = mcp_initialize(); mcp_initialized(sid)
    (_, f) = mcp_rpc(sid, 2, "tools/list", {})
    names = [t.name for t in f.result.tools]
    assert superset(names, ["oabp_list_missions","oabp_get_mission",
                            "oabp_create_mission","oabp_submit_mission","oabp_get_stats"])
    for t in f.result.tools: assert t.name and t.description and t.inputSchema
STEP "a session-less tools/call is rejected -32600, then succeeds with the session":
    sid = mcp_initialize(); mcp_initialized(sid)
    (r0, f0) = mcp_rpc(sid, 3, "tools/call",
                       { name:"oabp_get_stats", arguments:{} }, with_session=false)
    assert r0.status == 400 and f0.error.code == -32600          # "Missing session ID"
    (r1, f1) = mcp_rpc(sid, 4, "tools/call",
                       { name:"oabp_get_stats", arguments:{} }, with_session=true)
    assert f1.result.content[0].type == "text" and is_json(f1.result.content[0].text)

# ---- E: A2A JSON-RPC client -------------------------------------------------
FUNCTION a2a_rpc(id, method, params):
    r = HTTP.post(BASE+"/api/a2a",
                  headers={ "Content-Type":"application/json" },
                  body=json({ jsonrpc:"2.0", id:id, method:method, params:params }))
    return parse_json(r.body)

STEP "A2A message/send returns a Task":
    f = a2a_rpc(1, "message/send",
                { message:{ role:"user",
                            parts:[{ kind:"text", text:"list open missions" }],
                            messageId:fresh_uuid() } })
    assert f.jsonrpc == "2.0" and f.id == 1 and f.result is present
    task = f.result.task? OR f.result            # Task may be wrapped or be the result
    assert task.id is present and task.status.state is present
    world.tid = task.id
STEP "tasks/get and tasks/list operate on the returned task":
    g = a2a_rpc(2, "tasks/get", { id: world.tid })
    assert (g.result.id == world.tid) OR (g.result.task.id == world.tid)
    l = a2a_rpc(3, "tasks/list", {})
    assert any(t.id == world.tid for t in as_task_list(l.result))

# ---- reporting --------------------------------------------------------------
# Each scenario emits PASS / FAIL / SKIP keyed by its @CONF-* tag.
# CONFORMANCE  = every applicable @MUST scenario PASS.
# CONFORMANT-WITH-WARNINGS = a @SHOULD scenario FAIL (must be documented).
# FULL         = all @MUST PASS and >= 90% of @SHOULD PASS across all surfaces.
# Applicability tags gate execution:
#   @client-side             -> run only when an ES256/JCS verifier is under test
#   @session-using-server    -> @MUST only for servers that use MCP sessions
#   @write-gated             -> run only when the deployment gates writes
#   @mutating                -> requires permission to create/submit; else SKIP
# =============================================================================
