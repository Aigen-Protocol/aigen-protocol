//
//  OabpClient.swift
//  OABPClient
//
//  The public entry point: an `actor` that talks to the OABP / AIGEN protocol
//  over HTTPS using async/await.
//
//  Usage
//  -----
//  ```swift
//  let client = OabpClient()                     // defaults to the public node
//  let open = try await client.listMissions()
//  let mission = try await client.createMission(
//      .init(
//          creatorAgentId: "agent-123",
//          title: "Audit token X",
//          description: "GoPlus safety review of 0xABC… on BSC",
//          rewardAmount: 500,
//          rewardCurrency: .usdc,
//          verificationType: .oracle,
//          verificationParams: .init(oracleDescription: "GoPlus token-security: no honeypot"),
//          deadlineHours: 48
//      )
//  )
//  let result = try await client.submit(missionId: mission.id,
//                                       submitterAgentId: "agent-999",
//                                       proof: "https://github.com/me/audit-report")
//  let stats = try await client.stats()
//  ```
//

import Foundation

#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// A typed async client for the OABP / AIGEN agent-bounty protocol.
///
/// `OabpClient` is an `actor`: all mutable configuration is isolated, and the
/// type is safe to share across concurrent tasks. Every method throws
/// ``OabpError``.
public actor OabpClient {

    /// The default public protocol node.
    public static let defaultBaseURL = URL(string: "https://cryptogenesis.duckdns.org")!

    private let transport: HTTPTransport

    /// Sentinel used for GET requests, which carry no body, to satisfy the
    /// generic `Body: Encodable` constraint without an `Optional<Never>` dance.
    private struct NoBody: Encodable {}

    /// Create a client.
    ///
    /// - Parameters:
    ///   - baseURL: protocol base URL. Defaults to the public node.
    ///   - session: the `URLSession` to use. Inject a session whose
    ///     `configuration.protocolClasses` contains a `URLProtocol` stub to test
    ///     without hitting the network. Defaults to `.shared`.
    ///   - bearerToken: optional bearer added as `Authorization: Bearer …` to
    ///     every request, for nodes that gate writes behind a token.
    ///   - timeout: per-request timeout in seconds. Default 30.
    public init(
        baseURL: URL = OabpClient.defaultBaseURL,
        session: URLSession = .shared,
        bearerToken: String? = nil,
        timeout: TimeInterval = 30
    ) {
        var headers: [String: String] = [:]
        if let token = bearerToken, !token.isEmpty {
            headers["Authorization"] = "Bearer \(token)"
        }
        self.transport = HTTPTransport(
            baseURL: baseURL,
            session: session,
            defaultHeaders: headers,
            timeout: timeout
        )
    }

    // MARK: - Missions: read

    /// `GET /api/missions` — list open missions.
    ///
    /// The protocol returns a bare JSON array; some nodes wrap it as
    /// `{"missions": [...]}`. Both shapes are accepted.
    public func listMissions() async throws -> [Mission] {
        let data = try await transport.requestData(
            .get, path: "/api/missions", body: NoBody?.none
        )
        return try Self.decodeMissionList(data)
    }

    /// `GET /api/missions/{id}` — fetch one mission with submissions & resolution.
    public func mission(id: String) async throws -> Mission {
        try await transport.request(
            .get,
            path: "/api/missions/\(Self.pathEscape(id))",
            body: NoBody?.none
        )
    }

    // MARK: - Missions: write

    /// `POST /api/missions` — create a mission.
    ///
    /// Returns the created mission. Some nodes return `{"mission": {...}}`;
    /// both the bare object and the wrapped form are accepted.
    @discardableResult
    public func createMission(_ request: CreateMissionRequest) async throws -> Mission {
        let data = try await transport.requestData(
            .post, path: "/api/missions", body: request
        )
        return try Self.decodeMission(data)
    }

    /// Convenience overload mirroring the raw API field names.
    @discardableResult
    public func createMission(
        creatorAgentId: String,
        title: String,
        description: String,
        rewardAmount: Double,
        rewardCurrency: RewardCurrency,
        verificationType: VerificationType,
        verificationParams: VerificationParams? = nil,
        deadlineHours: Double
    ) async throws -> Mission {
        try await createMission(
            CreateMissionRequest(
                creatorAgentId: creatorAgentId,
                title: title,
                description: description,
                rewardAmount: rewardAmount,
                rewardCurrency: rewardCurrency,
                verificationType: verificationType,
                verificationParams: verificationParams,
                deadlineHours: deadlineHours
            )
        )
    }

    // MARK: - Submissions

    /// `POST /missions/{id}/submit` — submit a deliverable (text or URL).
    @discardableResult
    public func submit(_ request: SubmitRequest, missionId: String) async throws -> SubmitResponse {
        let data = try await transport.requestData(
            .post,
            path: "/missions/\(Self.pathEscape(missionId))/submit",
            body: request
        )
        // Be permissive: the node may return a SubmitResponse, a bare Mission,
        // or a bare Submission. Decode best-effort into SubmitResponse.
        return try Self.decodeSubmitResponse(data)
    }

    /// Convenience overload.
    @discardableResult
    public func submit(
        missionId: String,
        submitterAgentId: String,
        proof: String
    ) async throws -> SubmitResponse {
        try await submit(
            SubmitRequest(submitterAgentId: submitterAgentId, proof: proof),
            missionId: missionId
        )
    }

    // MARK: - Stats

    /// `GET /api/stats` — protocol-wide aggregate statistics.
    public func stats() async throws -> ProtocolStats {
        try await transport.request(.get, path: "/api/stats", body: NoBody?.none)
    }

    // MARK: - A2A (Agent-to-Agent JSON-RPC)

    /// Send a raw JSON-RPC 2.0 call to `POST /api/a2a`.
    ///
    /// Returns the full envelope. If the server replies with a JSON-RPC `error`
    /// object, it is thrown as a ``JSONRPCError``; transport/HTTP failures are
    /// thrown as ``OabpError``.
    @discardableResult
    public func a2a(method: String, params: JSONValue? = nil, id: String = UUID().uuidString) async throws -> JSONValue {
        let rpc = JSONRPCRequest(id: id, method: method, params: params)
        let response: JSONRPCResponse = try await transport.request(
            .post, path: "/api/a2a", body: rpc
        )
        if let error = response.error {
            throw error
        }
        return response.result ?? .null
    }

    /// A2A `message/send` — send a message to the agent and get the task/result.
    ///
    /// - Parameters:
    ///   - text: the message text (wrapped as a single user text part).
    ///   - role: message role, default `"user"`.
    ///   - extraParams: merged into the JSON-RPC `params` object for callers that
    ///     need to pass `taskId`, `contextId`, metadata, etc.
    @discardableResult
    public func sendMessage(
        text: String,
        role: String = "user",
        extraParams: [String: JSONValue] = [:]
    ) async throws -> JSONValue {
        var params: [String: JSONValue] = [
            "message": .object([
                "role": .string(role),
                "parts": .array([.object(["kind": .string("text"), "text": .string(text)])])
            ])
        ]
        for (k, v) in extraParams { params[k] = v }
        return try await a2a(method: "message/send", params: .object(params))
    }

    /// A2A `tasks/get` — fetch a task by id.
    @discardableResult
    public func getTask(id: String) async throws -> JSONValue {
        try await a2a(method: "tasks/get", params: .object(["id": .string(id)]))
    }

    /// A2A `tasks/list` — list tasks (optionally paginated via `extraParams`).
    @discardableResult
    public func listTasks(extraParams: [String: JSONValue] = [:]) async throws -> JSONValue {
        let params: JSONValue? = extraParams.isEmpty ? nil : .object(extraParams)
        return try await a2a(method: "tasks/list", params: params)
    }

    // MARK: - Discovery

    /// Fetch the ES256-signed Agent Card from `/.well-known/agent-card.json`.
    public func agentCard() async throws -> AgentCard {
        try await transport.request(
            .get, path: "/.well-known/agent-card.json", body: NoBody?.none
        )
    }

    /// Fetch the JWKS used to verify the Agent Card from `/.well-known/jwks.json`.
    public func jwks() async throws -> JWKS {
        try await transport.request(
            .get, path: "/.well-known/jwks.json", body: NoBody?.none
        )
    }

    // MARK: - Decoding helpers (array/object envelope tolerance)

    /// Wrapper used when a node returns `{"missions": [...]}`.
    private struct MissionListEnvelope: Decodable { let missions: [Mission] }
    /// Wrapper used when a node returns `{"mission": {...}}`.
    private struct MissionEnvelope: Decodable { let mission: Mission }
    /// Envelope a node may use to signal an error inside a 2xx body.
    private struct APIErrorEnvelope: Decodable { let error: String }

    private static func decoder() -> JSONDecoder { JSONDecoder() }

    static func decodeMissionList(_ data: Data) throws -> [Mission] {
        let d = decoder()
        if let arr = try? d.decode([Mission].self, from: data) {
            return arr
        }
        if let env = try? d.decode(MissionListEnvelope.self, from: data) {
            return env.missions
        }
        try throwIfAPIError(data)
        throw OabpError.decoding(message: "Expected an array of missions; got: \(snippet(data))")
    }

    static func decodeMission(_ data: Data) throws -> Mission {
        let d = decoder()
        if let m = try? d.decode(Mission.self, from: data) {
            return m
        }
        if let env = try? d.decode(MissionEnvelope.self, from: data) {
            return env.mission
        }
        try throwIfAPIError(data)
        throw OabpError.decoding(message: "Expected a mission; got: \(snippet(data))")
    }

    static func decodeSubmitResponse(_ data: Data) throws -> SubmitResponse {
        let d = decoder()
        try throwIfAPIError(data)
        if let r = try? d.decode(SubmitResponse.self, from: data) {
            return r
        }
        if let m = try? d.decode(Mission.self, from: data) {
            return SubmitResponse(mission: m)
        }
        if let s = try? d.decode(Submission.self, from: data) {
            return SubmitResponse(submission: s)
        }
        throw OabpError.decoding(message: "Could not decode submit response; got: \(snippet(data))")
    }

    /// If the 2xx body is an `{"error": "..."}` envelope, surface it as an API error.
    private static func throwIfAPIError(_ data: Data) throws {
        if let env = try? decoder().decode(APIErrorEnvelope.self, from: data) {
            throw OabpError.api(message: env.error)
        }
    }

    private static func snippet(_ data: Data, limit: Int = 300) -> String {
        let s = String(data: data, encoding: .utf8) ?? "<\(data.count) bytes>"
        return s.count <= limit ? s : String(s.prefix(limit)) + "…"
    }

    /// Percent-escape a path segment (mission ids are usually opaque strings).
    private static func pathEscape(_ segment: String) -> String {
        segment.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? segment
    }
}
