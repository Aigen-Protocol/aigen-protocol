//
//  ModelCodingTests.swift
//  OABPClientTests
//
//  Pure (no-network) Codable round-trip and JSONValue behaviour tests.
//

import XCTest
@testable import OABPClient

final class ModelCodingTests: XCTestCase {

    // MARK: - JSONValue

    func testJSONValueRoundTrip() throws {
        let value: JSONValue = [
            "s": "hello",
            "i": 42,
            "d": 3.5,
            "b": true,
            "n": nil,
            "arr": [1, 2, 3],
            "obj": ["nested": "yes"]
        ]
        let data = try JSONEncoder().encode(value)
        let decoded = try JSONDecoder().decode(JSONValue.self, from: data)
        XCTAssertEqual(decoded, value)

        // Accessors
        XCTAssertEqual(decoded["s"]?.stringValue, "hello")
        XCTAssertEqual(decoded["i"]?.intValue, 42)
        XCTAssertEqual(decoded["d"]?.doubleValue, 3.5)
        XCTAssertEqual(decoded["b"]?.boolValue, true)
        XCTAssertEqual(decoded["arr"]?[1]?.intValue, 2)
        XCTAssertEqual(decoded["obj"]?["nested"]?.stringValue, "yes")
        XCTAssertNil(decoded["missing"])
    }

    func testJSONValueNullEncodesAsNull() throws {
        let data = try JSONEncoder().encode(JSONValue.null)
        XCTAssertEqual(String(data: data, encoding: .utf8), "null")
    }

    // MARK: - Mission round-trip via snake_case

    func testMissionDecodesSnakeCaseKeys() throws {
        let raw = """
        {
          "id": "m1",
          "title": "T",
          "description": "D",
          "reward": {"amount": 12.5, "currency": "AIGEN"},
          "verification_type": "first_valid_match",
          "verification_params": {"regex": "abc"},
          "deadline": 1700000000,
          "status": "open",
          "creator_agent_id": "c1",
          "submissions": []
        }
        """
        let m = try JSONDecoder().decode(Mission.self, from: Data(raw.utf8))
        XCTAssertEqual(m.id, "m1")
        XCTAssertEqual(m.reward.amount, 12.5)
        XCTAssertEqual(m.reward.currency, .aigen)
        XCTAssertEqual(m.verificationType, .firstValidMatch)
        XCTAssertEqual(m.verificationParams?.regex, "abc")
        XCTAssertEqual(m.creatorAgentId, "c1")

        // Re-encode and confirm the snake_case keys come back out.
        let out = try JSONEncoder().encode(m)
        let obj = try JSONSerialization.jsonObject(with: out) as! [String: Any]
        XCTAssertNotNil(obj["verification_type"])
        XCTAssertNotNil(obj["verification_params"])
        XCTAssertNotNil(obj["creator_agent_id"])
        XCTAssertEqual(obj["verification_type"] as? String, "first_valid_match")
    }

    func testCreateMissionRequestEncoding() throws {
        let req = CreateMissionRequest(
            creatorAgentId: "a1",
            title: "Title",
            description: "Desc",
            rewardAmount: 100,
            rewardCurrency: .usdc,
            verificationType: .oracle,
            verificationParams: VerificationParams(oracleDescription: "GitHub repo in Go"),
            deadlineHours: 24
        )
        let data = try JSONEncoder().encode(req)
        let obj = try JSONSerialization.jsonObject(with: data) as! [String: Any]
        XCTAssertEqual(obj["creator_agent_id"] as? String, "a1")
        XCTAssertEqual(obj["reward_amount"] as? Double, 100)
        XCTAssertEqual(obj["reward_currency"] as? String, "USDC")
        XCTAssertEqual(obj["verification_type"] as? String, "oracle")
        XCTAssertEqual(obj["deadline_hours"] as? Double, 24)
        let vp = obj["verification_params"] as! [String: Any]
        XCTAssertEqual(vp["oracle_description"] as? String, "GitHub repo in Go")
        // first_valid_match-only key must be absent.
        XCTAssertNil(vp["regex"])
    }

    func testRewardCurrencyRawValues() {
        XCTAssertEqual(RewardCurrency.aigen.rawValue, "AIGEN")
        XCTAssertEqual(RewardCurrency.usdc.rawValue, "USDC")
        XCTAssertEqual(RewardCurrency(rawValue: "aigen"), .aigen) // case-insensitive
        XCTAssertEqual(RewardCurrency(rawValue: "weird"), .other("weird"))
    }

    func testVerificationTypeRawValues() {
        XCTAssertEqual(VerificationType.firstValidMatch.rawValue, "first_valid_match")
        XCTAssertEqual(VerificationType.peerVote.rawValue, "peer_vote")
        XCTAssertEqual(VerificationType.creatorJudges.rawValue, "creator_judges")
        XCTAssertEqual(VerificationType(rawValue: "oracle"), .oracle)
    }

    func testStatsDecoding() throws {
        let raw = #"{"resolved": 3, "open": 9, "lifetime_reward_aigen_paid": 1234.0}"#
        let s = try JSONDecoder().decode(ProtocolStats.self, from: Data(raw.utf8))
        XCTAssertEqual(s.resolved, 3)
        XCTAssertEqual(s.open, 9)
        XCTAssertEqual(s.lifetimeRewardAigenPaid, 1234.0)
    }

    func testOabpErrorDescriptions() {
        XCTAssertEqual(
            OabpError.httpStatus(code: 404, body: "not found").errorDescription,
            "HTTP 404: not found"
        )
        XCTAssertEqual(
            OabpError.httpStatus(code: 500, body: "   ").errorDescription,
            "HTTP 500"
        )
        XCTAssertEqual(
            OabpError.api(message: "bad").errorDescription,
            "API error: bad"
        )
    }
}
