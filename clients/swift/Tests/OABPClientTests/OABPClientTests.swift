//
//  OABPClientTests.swift
//  OABPClientTests
//
//  Network-free tests driving `OabpClient` through a `URLProtocol` stub.
//  They assert both decoding of canned responses and the *shape of outgoing
//  requests* (method, path, snake_case JSON body).
//

import XCTest
@testable import OABPClient

final class OABPClientTests: XCTestCase {

    private var client: OabpClient!
    private let base = URL(string: "https://cryptogenesis.duckdns.org")!

    override func setUp() {
        super.setUp()
        StubURLProtocol.reset()
        client = OabpClient(baseURL: base, session: StubURLProtocol.makeSession())
    }

    override func tearDown() {
        StubURLProtocol.reset()
        client = nil
        super.tearDown()
    }

    // MARK: Helpers

    private func json(_ string: String, status: Int = 200) -> StubURLProtocol.Outcome {
        .response(statusCode: status,
                  headers: ["Content-Type": "application/json"],
                  body: Data(string.utf8))
    }

    private func bodyJSON(of captured: StubURLProtocol.CapturedRequest) throws -> [String: Any] {
        let data = try XCTUnwrap(captured.body, "request had no body")
        let obj = try JSONSerialization.jsonObject(with: data)
        return try XCTUnwrap(obj as? [String: Any], "body was not a JSON object")
    }

    // MARK: - listMissions

    func testListMissionsBareArray() async throws {
        StubURLProtocol.setHandler { _ in
            self.json("""
            [
              {
                "id": "m1",
                "title": "Audit token X",
                "description": "GoPlus review",
                "reward": {"amount": 500, "currency": "USDC"},
                "verification_type": "oracle",
                "verification_params": {"oracle_description": "no honeypot"},
                "deadline": 1900000000,
                "status": "open",
                "submissions": []
              },
              {
                "id": 2,
                "title": "Find string",
                "description": "regex match",
                "reward": {"amount": 1000, "currency": "AIGEN"},
                "verification_type": "first_valid_match",
                "verification_params": {"regex": "^0x[a-f0-9]{40}$"},
                "deadline": 1900000111,
                "status": "open",
                "submissions": []
              }
            ]
            """)
        }

        let missions = try await client.listMissions()
        XCTAssertEqual(missions.count, 2)
        XCTAssertEqual(missions[0].id, "m1")
        XCTAssertEqual(missions[0].reward.currency, .usdc)
        XCTAssertEqual(missions[0].reward.amount, 500)
        XCTAssertEqual(missions[0].verificationType, .oracle)
        XCTAssertEqual(missions[0].verificationParams?.oracleDescription, "no honeypot")
        // Integer id must be coerced to a String.
        XCTAssertEqual(missions[1].id, "2")
        XCTAssertEqual(missions[1].verificationType, .firstValidMatch)
        XCTAssertEqual(missions[1].verificationParams?.regex, "^0x[a-f0-9]{40}$")

        // Outgoing request shape.
        let captured = try XCTUnwrap(StubURLProtocol.capturedRequests.first)
        XCTAssertEqual(captured.request.httpMethod, "GET")
        XCTAssertEqual(captured.request.url?.path, "/api/missions")
    }

    func testListMissionsWrappedEnvelope() async throws {
        StubURLProtocol.setHandler { _ in
            self.json("""
            {"missions": [
              {"id":"x","title":"t","description":"d",
               "reward":{"amount":1,"currency":"AIGEN"},
               "verification_type":"peer_vote","deadline":1,"status":"open","submissions":[]}
            ]}
            """)
        }
        let missions = try await client.listMissions()
        XCTAssertEqual(missions.count, 1)
        XCTAssertEqual(missions[0].verificationType, .peerVote)
    }

    // MARK: - mission(id:)

    func testGetMissionDetail() async throws {
        StubURLProtocol.setHandler { _ in
            self.json("""
            {
              "id": "abc-123",
              "title": "Repo deliverable",
              "description": "Build a Go CLI",
              "reward": {"amount": 250.5, "currency": "USDC"},
              "verification_type": "oracle",
              "verification_params": {"oracle_description": "GitHub repo in Go"},
              "deadline": 1888888888,
              "status": "resolved",
              "creator_agent_id": "creator-1",
              "submissions": [
                {"id":"s1","submitter_agent_id":"agent-9","proof":"https://github.com/a/b","verified":true}
              ],
              "resolution": {
                "winner_agent_id":"agent-9",
                "winning_proof":"https://github.com/a/b",
                "reward_paid":248.75,
                "protocol_fee":1.25,
                "resolved_at":1888889000
              }
            }
            """)
        }

        let m = try await client.mission(id: "abc-123")
        XCTAssertEqual(m.id, "abc-123")
        XCTAssertEqual(m.status, .resolved)
        XCTAssertEqual(m.creatorAgentId, "creator-1")
        XCTAssertEqual(m.submissions.count, 1)
        XCTAssertEqual(m.submissions[0].submitterAgentId, "agent-9")
        XCTAssertEqual(m.submissions[0].verified, true)
        XCTAssertEqual(m.resolution?.winnerAgentId, "agent-9")
        XCTAssertEqual(m.resolution?.rewardPaid, 248.75)
        XCTAssertEqual(m.resolution?.protocolFee, 1.25)

        let captured = try XCTUnwrap(StubURLProtocol.capturedRequests.first)
        XCTAssertEqual(captured.request.url?.path, "/api/missions/abc-123")
        XCTAssertEqual(captured.request.httpMethod, "GET")
    }

    // MARK: - createMission

    func testCreateMissionSendsSnakeCaseBody() async throws {
        StubURLProtocol.setHandler { _ in
            self.json("""
            {"id":"created-1","title":"Audit","description":"desc",
             "reward":{"amount":500,"currency":"USDC"},
             "verification_type":"oracle",
             "verification_params":{"oracle_description":"no honeypot"},
             "deadline":1900000000,"status":"open","submissions":[]}
            """, status: 201)
        }

        let created = try await client.createMission(
            creatorAgentId: "agent-123",
            title: "Audit",
            description: "desc",
            rewardAmount: 500,
            rewardCurrency: .usdc,
            verificationType: .oracle,
            verificationParams: VerificationParams(oracleDescription: "no honeypot"),
            deadlineHours: 48
        )
        XCTAssertEqual(created.id, "created-1")
        XCTAssertEqual(created.status, .open)

        let captured = try XCTUnwrap(StubURLProtocol.capturedRequests.first)
        XCTAssertEqual(captured.request.httpMethod, "POST")
        XCTAssertEqual(captured.request.url?.path, "/api/missions")
        XCTAssertEqual(
            captured.request.value(forHTTPHeaderField: "Content-Type"),
            "application/json"
        )

        let body = try bodyJSON(of: captured)
        XCTAssertEqual(body["creator_agent_id"] as? String, "agent-123")
        XCTAssertEqual(body["title"] as? String, "Audit")
        XCTAssertEqual(body["reward_amount"] as? Double, 500)
        XCTAssertEqual(body["reward_currency"] as? String, "USDC")
        XCTAssertEqual(body["verification_type"] as? String, "oracle")
        XCTAssertEqual(body["deadline_hours"] as? Double, 48)
        let vp = try XCTUnwrap(body["verification_params"] as? [String: Any])
        XCTAssertEqual(vp["oracle_description"] as? String, "no honeypot")
    }

    // MARK: - submit

    func testSubmitSendsProofAndDecodesResponse() async throws {
        StubURLProtocol.setHandler { _ in
            self.json("""
            {"accepted": true,
             "submission": {"id":"s9","submitter_agent_id":"agent-999","proof":"https://github.com/me/x","verified":true},
             "resolution": {"winner_agent_id":"agent-999","reward_paid":497.5,"protocol_fee":2.5}}
            """)
        }

        let result = try await client.submit(
            missionId: "m-42",
            submitterAgentId: "agent-999",
            proof: "https://github.com/me/x"
        )
        XCTAssertEqual(result.accepted, true)
        XCTAssertEqual(result.submission?.id, "s9")
        XCTAssertEqual(result.resolution?.winnerAgentId, "agent-999")
        XCTAssertEqual(result.resolution?.rewardPaid, 497.5)

        let captured = try XCTUnwrap(StubURLProtocol.capturedRequests.first)
        XCTAssertEqual(captured.request.httpMethod, "POST")
        XCTAssertEqual(captured.request.url?.path, "/missions/m-42/submit")
        let body = try bodyJSON(of: captured)
        XCTAssertEqual(body["submitter_agent_id"] as? String, "agent-999")
        XCTAssertEqual(body["proof"] as? String, "https://github.com/me/x")
    }

    func testSubmitAcceptsBareMissionResponse() async throws {
        // Node returns the updated mission instead of a SubmitResponse envelope.
        StubURLProtocol.setHandler { _ in
            self.json("""
            {"id":"m-42","title":"t","description":"d",
             "reward":{"amount":1,"currency":"AIGEN"},
             "verification_type":"first_valid_match","deadline":1,"status":"open",
             "submissions":[{"submitter_agent_id":"agent-1","proof":"hello"}]}
            """)
        }
        let result = try await client.submit(
            missionId: "m-42", submitterAgentId: "agent-1", proof: "hello"
        )
        XCTAssertEqual(result.mission?.id, "m-42")
        XCTAssertEqual(result.mission?.submissions.first?.proof, "hello")
    }

    // MARK: - stats

    func testStats() async throws {
        StubURLProtocol.setHandler { _ in
            self.json("""
            {"resolved": 12, "open": 7, "lifetime_reward_aigen_paid": 108000.5}
            """)
        }
        let stats = try await client.stats()
        XCTAssertEqual(stats.resolved, 12)
        XCTAssertEqual(stats.open, 7)
        XCTAssertEqual(stats.lifetimeRewardAigenPaid, 108000.5)

        let captured = try XCTUnwrap(StubURLProtocol.capturedRequests.first)
        XCTAssertEqual(captured.request.url?.path, "/api/stats")
        XCTAssertEqual(captured.request.httpMethod, "GET")
    }

    // MARK: - A2A

    func testSendMessageJSONRPC() async throws {
        StubURLProtocol.setHandler { _ in
            self.json("""
            {"jsonrpc":"2.0","id":"req-1",
             "result":{"id":"task-7","status":{"state":"completed"},
                       "artifacts":[{"parts":[{"kind":"text","text":"pong"}]}]}}
            """)
        }

        let result = try await client.sendMessage(text: "ping")
        // Navigate the dynamic result.
        XCTAssertEqual(result["id"]?.stringValue, "task-7")
        XCTAssertEqual(result["status"]?["state"]?.stringValue, "completed")
        let text = result["artifacts"]?[0]?["parts"]?[0]?["text"]?.stringValue
        XCTAssertEqual(text, "pong")

        // Outgoing JSON-RPC envelope.
        let captured = try XCTUnwrap(StubURLProtocol.capturedRequests.first)
        XCTAssertEqual(captured.request.url?.path, "/api/a2a")
        XCTAssertEqual(captured.request.httpMethod, "POST")
        let body = try bodyJSON(of: captured)
        XCTAssertEqual(body["jsonrpc"] as? String, "2.0")
        XCTAssertEqual(body["method"] as? String, "message/send")
        let params = try XCTUnwrap(body["params"] as? [String: Any])
        let message = try XCTUnwrap(params["message"] as? [String: Any])
        XCTAssertEqual(message["role"] as? String, "user")
        let parts = try XCTUnwrap(message["parts"] as? [[String: Any]])
        XCTAssertEqual(parts.first?["text"] as? String, "ping")
    }

    func testA2AErrorIsThrown() async throws {
        StubURLProtocol.setHandler { _ in
            self.json("""
            {"jsonrpc":"2.0","id":"req-1",
             "error":{"code":-32601,"message":"Method not found"}}
            """)
        }
        do {
            _ = try await client.getTask(id: "nope")
            XCTFail("expected JSONRPCError")
        } catch let error as JSONRPCError {
            XCTAssertEqual(error.code, -32601)
            XCTAssertEqual(error.message, "Method not found")
        }
    }

    func testListTasks() async throws {
        StubURLProtocol.setHandler { _ in
            self.json("""
            {"jsonrpc":"2.0","id":"r","result":{"tasks":[{"id":"t1"},{"id":"t2"}]}}
            """)
        }
        let result = try await client.listTasks()
        XCTAssertEqual(result["tasks"]?.arrayValue?.count, 2)
        let captured = try XCTUnwrap(StubURLProtocol.capturedRequests.first)
        let body = try bodyJSON(of: captured)
        XCTAssertEqual(body["method"] as? String, "tasks/list")
    }

    // MARK: - Discovery

    func testAgentCardAndJWKS() async throws {
        StubURLProtocol.setHandler { request in
            if request.url?.path == "/.well-known/agent-card.json" {
                return self.json("""
                {"name":"AIGEN Agent","description":"OABP node","url":"https://cryptogenesis.duckdns.org/api/a2a",
                 "version":"1.0.0","capabilities":{"streaming":false}}
                """)
            }
            if request.url?.path == "/.well-known/jwks.json" {
                return self.json("""
                {"keys":[{"kty":"EC","crv":"P-256","x":"abc","y":"def","kid":"key-1","alg":"ES256","use":"sig"}]}
                """)
            }
            return self.json("{}", status: 404)
        }

        let card = try await client.agentCard()
        XCTAssertEqual(card.name, "AIGEN Agent")
        XCTAssertEqual(card.version, "1.0.0")

        let jwks = try await client.jwks()
        XCTAssertEqual(jwks.keys.count, 1)
        XCTAssertEqual(jwks.keys[0].crv, "P-256")
        XCTAssertEqual(jwks.keys[0].alg, "ES256")
    }

    // MARK: - Error handling

    func testHTTPErrorIsMapped() async throws {
        StubURLProtocol.setHandler { _ in
            self.json("""
            {"error":"mission not found"}
            """, status: 404)
        }
        do {
            _ = try await client.mission(id: "missing")
            XCTFail("expected OabpError.httpStatus")
        } catch let error as OabpError {
            guard case let .httpStatus(code, body) = error else {
                return XCTFail("expected httpStatus, got \(error)")
            }
            XCTAssertEqual(code, 404)
            XCTAssertTrue(body.contains("mission not found"))
        }
    }

    func testAPIErrorEnvelopeInside2xx() async throws {
        StubURLProtocol.setHandler { _ in
            self.json("""
            {"error":"deadline must be positive"}
            """, status: 200)
        }
        do {
            _ = try await client.createMission(
                creatorAgentId: "a", title: "t", description: "d",
                rewardAmount: 1, rewardCurrency: .aigen,
                verificationType: .firstValidMatch, deadlineHours: -1
            )
            XCTFail("expected OabpError.api")
        } catch let error as OabpError {
            guard case let .api(message) = error else {
                return XCTFail("expected api error, got \(error)")
            }
            XCTAssertEqual(message, "deadline must be positive")
        }
    }

    func testTransportFailureIsMapped() async throws {
        struct Boom: Error {}
        StubURLProtocol.setHandler { _ in .failure(Boom()) }
        do {
            _ = try await client.listMissions()
            XCTFail("expected OabpError.transport")
        } catch let error as OabpError {
            guard case .transport = error else {
                return XCTFail("expected transport error, got \(error)")
            }
        }
    }

    // MARK: - Enum tolerance

    func testUnknownEnumValuesDecodeToOther() async throws {
        StubURLProtocol.setHandler { _ in
            self.json("""
            [{"id":"u","title":"t","description":"d",
              "reward":{"amount":1,"currency":"DOGE"},
              "verification_type":"zk_proof","deadline":1,"status":"frozen","submissions":[]}]
            """)
        }
        let missions = try await client.listMissions()
        XCTAssertEqual(missions[0].reward.currency, .other("DOGE"))
        XCTAssertEqual(missions[0].verificationType, .other("zk_proof"))
        XCTAssertEqual(missions[0].status, .other("frozen"))
    }

    // MARK: - Mission convenience

    func testMissionDeadlineHelpers() {
        let m = Mission(
            id: "m", title: "t", description: "d",
            reward: Reward(amount: 1, currency: .aigen),
            verificationType: .oracle,
            deadline: 1_000
        )
        XCTAssertEqual(m.deadlineDate, Date(timeIntervalSince1970: 1_000))
        XCTAssertTrue(m.isExpired(asOf: Date(timeIntervalSince1970: 2_000)))
        XCTAssertFalse(m.isExpired(asOf: Date(timeIntervalSince1970: 500)))
    }
}
