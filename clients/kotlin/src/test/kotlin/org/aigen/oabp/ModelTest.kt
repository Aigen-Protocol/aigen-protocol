package org.aigen.oabp

import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.aigen.oabp.model.CreateMissionRequest
import org.aigen.oabp.model.Currency
import org.aigen.oabp.model.Mission
import org.aigen.oabp.model.MissionStatus
import org.aigen.oabp.model.Resolution
import org.aigen.oabp.model.Reward
import org.aigen.oabp.model.Submission
import org.aigen.oabp.model.VerificationType
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertThrows
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.math.BigDecimal
import java.time.Instant

/** Pure model tests: no network, just (de)serialization and domain logic. */
class ModelTest {
    @Test
    fun reward_netAndFee_useExactBigDecimalMath() {
        val r = Reward(BigDecimal("1000"), Currency.USDC)
        assertEquals(0, BigDecimal("995.000").compareTo(r.netAmount))
        assertEquals(0, BigDecimal("5.000").compareTo(r.protocolFee))
    }

    @Test
    fun verificationType_isSealedAndExhaustive() {
        val all = VerificationType.known + VerificationType.Unknown("zk")
        for (vt in all) {
            // Compiles only because the hierarchy is sealed and handled exhaustively.
            val label =
                when (vt) {
                    VerificationType.FirstValidMatch -> "first_valid_match"
                    VerificationType.Oracle -> "oracle"
                    VerificationType.PeerVote -> "peer_vote"
                    VerificationType.CreatorJudges -> "creator_judges"
                    is VerificationType.Unknown -> vt.wire
                }
            assertEquals(vt.wire, label)
        }
    }

    @Test
    fun verificationType_fromWire_isCaseInsensitiveAndForwardCompatible() {
        assertEquals(VerificationType.FirstValidMatch, VerificationType.fromWire("FIRST_VALID_MATCH"))
        assertEquals(VerificationType.Oracle, VerificationType.fromWire("oracle"))
        val unknown = VerificationType.fromWire("peer_review_2")
        assertTrue(unknown is VerificationType.Unknown)
        assertEquals("peer_review_2", (unknown as VerificationType.Unknown).wire)
        assertEquals(VerificationType.Unknown(""), VerificationType.fromWire(null))
    }

    @Test
    fun currencyAndStatus_unknownWireMapsToSentinel() {
        assertEquals(Currency.UNKNOWN, Currency.fromWire("DOGE"))
        assertEquals(Currency.AIGEN, Currency.fromWire("aigen"))
        assertEquals(MissionStatus.UNKNOWN, MissionStatus.fromWire("paused"))
        assertEquals(MissionStatus.IN_REVIEW, MissionStatus.fromWire("in_review"))
        assertThrows(IllegalStateException::class.java) { Currency.UNKNOWN.wireValue() }
    }

    @Test
    fun submission_roundTripsUnixSecondsTimestamp() {
        val s =
            Submission(
                id = "s1",
                submitterAgentId = "a1",
                proof = "x",
                accepted = true,
                submittedAt = Instant.ofEpochSecond(1_700_000_000L),
            )
        val json = OabpJson.encodeToString(s)
        // Timestamp must be a bare number, not an ISO string.
        assertTrue(json.contains("\"submitted_at\":1700000000"), json)
        val back = OabpJson.decodeFromString<Submission>(json)
        assertEquals(s, back)
    }

    @Test
    fun submission_acceptsStringifiedTimestamp() {
        val back = OabpJson.decodeFromString<Submission>("""{"id":"s","submitted_at":"1700000000"}""")
        assertEquals(Instant.ofEpochSecond(1_700_000_000L), back.submittedAt)
    }

    @Test
    fun createMissionRequest_validatesRequiredFields() {
        assertThrows(IllegalArgumentException::class.java) {
            CreateMissionRequest.firstValidMatch("", "t", "d", 1, Currency.AIGEN, ".*", 1)
        }
        assertThrows(IllegalArgumentException::class.java) {
            CreateMissionRequest.oracle("c", "t", "d", 0, Currency.AIGEN, "desc", 1)
        }
        assertThrows(IllegalArgumentException::class.java) {
            CreateMissionRequest.oracle("c", "t", "d", 5, Currency.AIGEN, "desc", 0)
        }
    }

    @Test
    fun createMissionRequest_serializesToWireShape() {
        val req =
            CreateMissionRequest.oracle(
                creatorAgentId = "c1",
                title = "Audit",
                description = "GoPlus review of 0xabc",
                rewardAmount = BigDecimal("12.50"),
                rewardCurrency = Currency.USDC,
                oracleDescription = "GoPlus token-security",
                deadlineHours = 48,
            )
        val obj = Json.parseToJsonElement(OabpJson.encodeToString(req)).jsonObject
        assertEquals("c1", obj["creator_agent_id"]!!.jsonPrimitive.content)
        assertEquals("USDC", obj["reward_currency"]!!.jsonPrimitive.content)
        assertEquals("oracle", obj["verification_type"]!!.jsonPrimitive.content)
        assertEquals("12.50", obj["reward_amount"]!!.jsonPrimitive.content)
        assertEquals(
            "GoPlus token-security",
            obj["verification_params"]!!.jsonObject["oracle_description"]!!.jsonPrimitive.content,
        )
    }

    @Test
    fun mission_defaultsAndDeadlineLogic() {
        val m =
            Mission(
                id = "m",
                status = MissionStatus.OPEN,
                deadline = Instant.ofEpochSecond(1_000),
            )
        assertTrue(m.isOpen)
        assertTrue(m.submissions.isEmpty())
        assertTrue(m.isPastDeadline(Instant.ofEpochSecond(2_000)))
        assertFalse(m.isPastDeadline(Instant.ofEpochSecond(500)))
        // No-deadline mission is never past deadline.
        assertFalse(Mission(id = "x").isPastDeadline(Instant.now()))
    }

    @Test
    fun resolution_hasWinnerReflectsPresence() {
        assertTrue(Resolution(winnerAgentId = "a").hasWinner)
        assertFalse(Resolution(winnerAgentId = "  ").hasWinner)
        assertFalse(Resolution().hasWinner)
    }
}
