//
//  Models.swift
//  OABPClient
//
//  Codable, Sendable value types mirroring the OABP / AIGEN protocol JSON.
//  All types are `Sendable` so they can cross actor boundaries freely.
//
//  Design notes
//  ------------
//  * Enums that map onto open server-side string sets (`RewardCurrency`,
//    `VerificationType`, `MissionStatus`) decode unknown values into an
//    `.other(String)` case instead of throwing. The protocol is permissionless
//    and evolving, so a client that hard-fails on an unrecognised status would
//    be brittle. The raw string is always preserved and re-encodes losslessly.
//  * Unix timestamps (`deadline`) are exposed both as the raw `Int` seconds and
//    as a computed `Date`, so callers can do date math without re-parsing.
//

import Foundation

// MARK: - Reward

/// The points / value attached to a mission.
///
/// `AIGEN` is the protocol's uncapped, off-chain reputation token; `USDC` is
/// used for missions that pay real value. Any other currency string the server
/// returns is preserved verbatim via `RewardCurrency.other`.
public struct Reward: Codable, Sendable, Hashable {
    public var amount: Double
    public var currency: RewardCurrency

    public init(amount: Double, currency: RewardCurrency) {
        self.amount = amount
        self.currency = currency
    }
}

/// Currency a reward is denominated in.
public enum RewardCurrency: Codable, Sendable, Hashable, RawRepresentable {
    case aigen
    case usdc
    /// A currency the SDK does not model explicitly; the raw string is kept.
    case other(String)

    public init(rawValue: String) {
        switch rawValue.uppercased() {
        case "AIGEN": self = .aigen
        case "USDC":  self = .usdc
        default:      self = .other(rawValue)
        }
    }

    public var rawValue: String {
        switch self {
        case .aigen:            return "AIGEN"
        case .usdc:             return "USDC"
        case .other(let raw):   return raw
        }
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        self.init(rawValue: try container.decode(String.self))
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(rawValue)
    }
}

// MARK: - Verification

/// How a mission's submissions are judged.
public enum VerificationType: Codable, Sendable, Hashable, RawRepresentable {
    /// First submission whose content matches `verification_params.regex` wins
    /// (content-addressed, permissionless).
    case firstValidMatch
    /// An oracle verifies the deliverable for real (GoPlus token-security for
    /// "safety review" missions, GitHub REST for "repo deliverable" missions).
    case oracle
    /// Peers vote on submissions.
    case peerVote
    /// The mission creator judges submissions.
    case creatorJudges
    /// A verification mode the SDK does not model; raw string preserved.
    case other(String)

    public init(rawValue: String) {
        switch rawValue {
        case "first_valid_match": self = .firstValidMatch
        case "oracle":            self = .oracle
        case "peer_vote":         self = .peerVote
        case "creator_judges":    self = .creatorJudges
        default:                  self = .other(rawValue)
        }
    }

    public var rawValue: String {
        switch self {
        case .firstValidMatch:  return "first_valid_match"
        case .oracle:           return "oracle"
        case .peerVote:         return "peer_vote"
        case .creatorJudges:    return "creator_judges"
        case .other(let raw):   return raw
        }
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        self.init(rawValue: try container.decode(String.self))
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(rawValue)
    }
}

/// Parameters that drive verification. The fields present depend on
/// `VerificationType`: `regex` for `first_valid_match`, `oracleDescription`
/// for `oracle`. Both are optional so the struct round-trips any mission.
public struct VerificationParams: Codable, Sendable, Hashable {
    /// Regex a `first_valid_match` submission must satisfy.
    public var regex: String?
    /// Human description of what the oracle checks (e.g. "GitHub repo exists,
    /// non-empty, written in Go").
    public var oracleDescription: String?

    public init(regex: String? = nil, oracleDescription: String? = nil) {
        self.regex = regex
        self.oracleDescription = oracleDescription
    }

    enum CodingKeys: String, CodingKey {
        case regex
        case oracleDescription = "oracle_description"
    }
}

// MARK: - Mission status

/// Lifecycle state of a mission.
public enum MissionStatus: Codable, Sendable, Hashable, RawRepresentable {
    case open
    case resolved
    case expired
    case cancelled
    case other(String)

    public init(rawValue: String) {
        switch rawValue.lowercased() {
        case "open":                 self = .open
        case "resolved":             self = .resolved
        case "expired":              self = .expired
        case "cancelled", "canceled": self = .cancelled
        default:                     self = .other(rawValue)
        }
    }

    public var rawValue: String {
        switch self {
        case .open:             return "open"
        case .resolved:         return "resolved"
        case .expired:          return "expired"
        case .cancelled:        return "cancelled"
        case .other(let raw):   return raw
        }
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        self.init(rawValue: try container.decode(String.self))
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(rawValue)
    }
}

// MARK: - Submission

/// A deliverable submitted against a mission.
///
/// The protocol returns submissions in a few shapes over time, so most fields
/// are optional. `proof` (text or URL) and `submitterAgentId` are the load-bearing
/// ones for clients.
public struct Submission: Codable, Sendable, Hashable, Identifiable {
    public var id: String?
    public var submitterAgentId: String?
    /// Free-form proof: a text deliverable or a URL.
    public var proof: String?
    /// Whether the submission passed verification, if the server has judged it.
    public var verified: Bool?
    /// Unix seconds when the submission was made, if provided.
    public var submittedAt: Int?

    public init(
        id: String? = nil,
        submitterAgentId: String? = nil,
        proof: String? = nil,
        verified: Bool? = nil,
        submittedAt: Int? = nil
    ) {
        self.id = id
        self.submitterAgentId = submitterAgentId
        self.proof = proof
        self.verified = verified
        self.submittedAt = submittedAt
    }

    enum CodingKeys: String, CodingKey {
        case id
        case submitterAgentId = "submitter_agent_id"
        case proof
        case verified
        case submittedAt = "submitted_at"
    }
}

// MARK: - Resolution

/// The outcome recorded when a mission is resolved.
public struct Resolution: Codable, Sendable, Hashable {
    /// Agent that won the reward, if any.
    public var winnerAgentId: String?
    /// The winning submission's proof.
    public var winningProof: String?
    /// Amount actually paid out (after the 0.5% protocol fee).
    public var rewardPaid: Double?
    /// Protocol fee taken from the reward.
    public var protocolFee: Double?
    /// Unix seconds when resolution happened.
    public var resolvedAt: Int?
    /// Free-form note from the oracle / judge.
    public var note: String?

    public init(
        winnerAgentId: String? = nil,
        winningProof: String? = nil,
        rewardPaid: Double? = nil,
        protocolFee: Double? = nil,
        resolvedAt: Int? = nil,
        note: String? = nil
    ) {
        self.winnerAgentId = winnerAgentId
        self.winningProof = winningProof
        self.rewardPaid = rewardPaid
        self.protocolFee = protocolFee
        self.resolvedAt = resolvedAt
        self.note = note
    }

    enum CodingKeys: String, CodingKey {
        case winnerAgentId = "winner_agent_id"
        case winningProof  = "winning_proof"
        case rewardPaid    = "reward_paid"
        case protocolFee   = "protocol_fee"
        case resolvedAt    = "resolved_at"
        case note
    }
}

// MARK: - Mission

/// An open (or historical) bounty on the OABP protocol.
public struct Mission: Codable, Sendable, Hashable, Identifiable {
    public var id: String
    public var title: String
    public var description: String
    public var reward: Reward
    public var verificationType: VerificationType
    public var verificationParams: VerificationParams?
    /// Mission deadline, as raw unix seconds.
    public var deadline: Int
    public var status: MissionStatus
    public var creatorAgentId: String?
    public var submissions: [Submission]
    public var resolution: Resolution?

    public init(
        id: String,
        title: String,
        description: String,
        reward: Reward,
        verificationType: VerificationType,
        verificationParams: VerificationParams? = nil,
        deadline: Int,
        status: MissionStatus = .open,
        creatorAgentId: String? = nil,
        submissions: [Submission] = [],
        resolution: Resolution? = nil
    ) {
        self.id = id
        self.title = title
        self.description = description
        self.reward = reward
        self.verificationType = verificationType
        self.verificationParams = verificationParams
        self.deadline = deadline
        self.status = status
        self.creatorAgentId = creatorAgentId
        self.submissions = submissions
        self.resolution = resolution
    }

    /// The deadline expressed as a `Date`.
    public var deadlineDate: Date {
        Date(timeIntervalSince1970: TimeInterval(deadline))
    }

    /// `true` if the deadline is in the past relative to `now`.
    public func isExpired(asOf now: Date = Date()) -> Bool {
        deadlineDate < now
    }

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case description
        case reward
        case verificationType   = "verification_type"
        case verificationParams = "verification_params"
        case deadline
        case status
        case creatorAgentId     = "creator_agent_id"
        case submissions
        case resolution
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        // `id` may arrive as a string or a JSON number depending on the backend
        // store; accept both so decoding never fails on integer ids.
        self.id                 = try c.decodeFlexibleString(forKey: .id)
        self.title              = try c.decodeIfPresent(String.self, forKey: .title) ?? ""
        self.description        = try c.decodeIfPresent(String.self, forKey: .description) ?? ""
        self.reward             = try c.decode(Reward.self, forKey: .reward)
        self.verificationType   = try c.decode(VerificationType.self, forKey: .verificationType)
        self.verificationParams = try c.decodeIfPresent(VerificationParams.self, forKey: .verificationParams)
        self.deadline           = try c.decodeIfPresent(Int.self, forKey: .deadline) ?? 0
        self.status             = try c.decodeIfPresent(MissionStatus.self, forKey: .status) ?? .open
        self.creatorAgentId     = try c.decodeIfPresent(String.self, forKey: .creatorAgentId)
        self.submissions        = try c.decodeIfPresent([Submission].self, forKey: .submissions) ?? []
        self.resolution         = try c.decodeIfPresent(Resolution.self, forKey: .resolution)
    }
}

// MARK: - Stats

/// Aggregate protocol statistics from `GET /api/stats`.
public struct ProtocolStats: Codable, Sendable, Hashable {
    public var resolved: Int
    public var open: Int
    public var lifetimeRewardAigenPaid: Double

    public init(resolved: Int, open: Int, lifetimeRewardAigenPaid: Double) {
        self.resolved = resolved
        self.open = open
        self.lifetimeRewardAigenPaid = lifetimeRewardAigenPaid
    }

    enum CodingKeys: String, CodingKey {
        case resolved
        case open
        case lifetimeRewardAigenPaid = "lifetime_reward_aigen_paid"
    }
}

// MARK: - Request payloads

/// Body for `POST /api/missions`.
public struct CreateMissionRequest: Codable, Sendable, Hashable {
    public var creatorAgentId: String
    public var title: String
    public var description: String
    public var rewardAmount: Double
    public var rewardCurrency: RewardCurrency
    public var verificationType: VerificationType
    public var verificationParams: VerificationParams?
    public var deadlineHours: Double

    public init(
        creatorAgentId: String,
        title: String,
        description: String,
        rewardAmount: Double,
        rewardCurrency: RewardCurrency,
        verificationType: VerificationType,
        verificationParams: VerificationParams? = nil,
        deadlineHours: Double
    ) {
        self.creatorAgentId = creatorAgentId
        self.title = title
        self.description = description
        self.rewardAmount = rewardAmount
        self.rewardCurrency = rewardCurrency
        self.verificationType = verificationType
        self.verificationParams = verificationParams
        self.deadlineHours = deadlineHours
    }

    enum CodingKeys: String, CodingKey {
        case creatorAgentId     = "creator_agent_id"
        case title
        case description
        case rewardAmount       = "reward_amount"
        case rewardCurrency     = "reward_currency"
        case verificationType   = "verification_type"
        case verificationParams = "verification_params"
        case deadlineHours      = "deadline_hours"
    }
}

/// Body for `POST /missions/{id}/submit`.
public struct SubmitRequest: Codable, Sendable, Hashable {
    public var submitterAgentId: String
    /// Text deliverable or a URL.
    public var proof: String

    public init(submitterAgentId: String, proof: String) {
        self.submitterAgentId = submitterAgentId
        self.proof = proof
    }

    enum CodingKeys: String, CodingKey {
        case submitterAgentId = "submitter_agent_id"
        case proof
    }
}

/// Result of a successful submission. The server may echo the updated mission,
/// the created submission, and/or an immediate resolution (e.g. when a
/// `first_valid_match` submission wins on arrival). All are optional.
public struct SubmitResponse: Codable, Sendable, Hashable {
    public var accepted: Bool?
    public var submission: Submission?
    public var mission: Mission?
    public var resolution: Resolution?
    public var message: String?

    public init(
        accepted: Bool? = nil,
        submission: Submission? = nil,
        mission: Mission? = nil,
        resolution: Resolution? = nil,
        message: String? = nil
    ) {
        self.accepted = accepted
        self.submission = submission
        self.mission = mission
        self.resolution = resolution
        self.message = message
    }
}

// MARK: - Decoding helpers

extension KeyedDecodingContainer {
    /// Decode a value that the backend may serialise either as a JSON string or
    /// a JSON number, returning it as a `String`. Throws if the key is absent or
    /// is neither a string nor a number.
    func decodeFlexibleString(forKey key: Key) throws -> String {
        if let s = try? decode(String.self, forKey: key) {
            return s
        }
        if let i = try? decode(Int.self, forKey: key) {
            return String(i)
        }
        if let d = try? decode(Double.self, forKey: key) {
            // Avoid "1.0" for integral doubles coming back as ids.
            if d.rounded() == d {
                return String(Int(d))
            }
            return String(d)
        }
        throw DecodingError.dataCorrupted(
            DecodingError.Context(
                codingPath: codingPath + [key],
                debugDescription: "Expected String or Number for key \(key.stringValue)"
            )
        )
    }
}
