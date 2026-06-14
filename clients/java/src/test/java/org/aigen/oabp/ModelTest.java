package org.aigen.oabp;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.aigen.oabp.model.CreateMissionRequest;
import org.aigen.oabp.model.Currency;
import org.aigen.oabp.model.Mission;
import org.aigen.oabp.model.MissionStatus;
import org.aigen.oabp.model.Reward;
import org.aigen.oabp.model.SubmitRequest;
import org.aigen.oabp.model.VerificationParams;
import org.aigen.oabp.model.VerificationType;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Instant;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** Pure unit tests for the model/value layer — no network. */
class ModelTest {

    private final ObjectMapper mapper = Json.newMapper();

    @Test
    void rewardNetAndFeeMath() {
        Reward r = new Reward(new BigDecimal("1000"), Currency.AIGEN);
        assertEquals(0, new BigDecimal("995.000").compareTo(r.netAmount()));
        assertEquals(0, new BigDecimal("5.000").compareTo(r.protocolFee()));
        assertEquals(0, new BigDecimal("0.005").compareTo(Reward.PROTOCOL_FEE_RATE));
    }

    @Test
    void rewardNormalizesNulls() {
        Reward r = new Reward(null, null);
        assertEquals(0, BigDecimal.ZERO.compareTo(r.amount()));
        assertEquals(Currency.UNKNOWN, r.currency());
    }

    @Test
    void builderRejectsMissingRequiredFields() {
        assertThrows(IllegalStateException.class, () -> CreateMissionRequest.builder()
                .title("t").description("d").rewardAmount(1).aigen()
                .verificationType(VerificationType.PEER_VOTE).deadlineHours(1)
                .build()); // missing creatorAgentId

        assertThrows(IllegalStateException.class, () -> CreateMissionRequest.builder()
                .creatorAgentId("c").title("t").description("d").rewardAmount(1).aigen()
                .verificationType(VerificationType.PEER_VOTE)
                .build()); // missing deadlineHours
    }

    @Test
    void builderRejectsInvalidValues() {
        assertThrows(IllegalArgumentException.class, () -> CreateMissionRequest.builder()
                .creatorAgentId("c").title("t").description("d")
                .rewardAmount(0).aigen()
                .verificationType(VerificationType.PEER_VOTE).deadlineHours(1)
                .build()); // reward must be > 0

        assertThrows(IllegalArgumentException.class, () -> CreateMissionRequest.builder()
                .creatorAgentId("c").title("t").description("d")
                .rewardAmount(5).aigen()
                .verificationType(VerificationType.PEER_VOTE).deadlineHours(0)
                .build()); // deadlineHours must be > 0
    }

    @Test
    void builderBuildsValidPeerVoteRequest() {
        CreateMissionRequest req = CreateMissionRequest.builder()
                .creatorAgentId("c").title("t").description("d")
                .rewardAmount("12.5").aigen()
                .verificationType(VerificationType.PEER_VOTE)
                .deadlineHours(24)
                .build();
        assertEquals(Currency.AIGEN, req.rewardCurrency());
        assertEquals(0, new BigDecimal("12.5").compareTo(req.rewardAmount()));
        assertEquals(VerificationParams.empty(), req.verificationParams());
    }

    @Test
    void submitRequestValidatesInputs() {
        assertThrows(IllegalArgumentException.class, () -> new SubmitRequest("", "proof"));
        assertThrows(IllegalArgumentException.class, () -> new SubmitRequest("agent", " "));
        SubmitRequest ok = new SubmitRequest("agent", "proof");
        assertEquals("agent", ok.submitterAgentId());
    }

    @Test
    void enumParsingIsCaseInsensitiveAndForwardCompatible() {
        assertEquals(Currency.AIGEN, Currency.fromWire("aigen"));
        assertEquals(Currency.USDC, Currency.fromWire("USDC"));
        assertEquals(Currency.UNKNOWN, Currency.fromWire("eth"));
        assertEquals(Currency.UNKNOWN, Currency.fromWire(null));

        assertEquals(VerificationType.ORACLE, VerificationType.fromWire("ORACLE"));
        assertEquals(VerificationType.FIRST_VALID_MATCH,
                VerificationType.fromWire("first_valid_match"));
        assertEquals(VerificationType.UNKNOWN, VerificationType.fromWire("???"));

        assertEquals(MissionStatus.RESOLVED, MissionStatus.fromWire("resolved"));
        assertTrue(MissionStatus.EXPIRED.isTerminal());
        assertFalse(MissionStatus.OPEN.isTerminal());
    }

    @Test
    void unknownCurrencyHasNoWireValue() {
        assertThrows(IllegalStateException.class, Currency.UNKNOWN::wireValue);
        assertEquals("AIGEN", Currency.AIGEN.wireValue());
    }

    @Test
    void missionRoundTripsThroughJackson() throws Exception {
        String json = """
                {"id":"m1","title":"t","description":"d",
                 "reward":{"amount":7,"currency":"AIGEN"},
                 "verification_type":"first_valid_match",
                 "verification_params":{"regex":"x"},
                 "deadline":1893456000,"status":"open","submissions":[]}
                """;
        Mission m = mapper.readValue(json, Mission.class);
        String back = mapper.writeValueAsString(m);
        Mission m2 = mapper.readValue(back, Mission.class);
        assertEquals(m.id(), m2.id());
        assertEquals(m.deadline(), m2.deadline());
        assertEquals(Instant.ofEpochSecond(1893456000L), m2.deadline());
        // deadline must serialize as an integer (unix seconds), not an ISO string/array.
        assertTrue(back.contains("\"deadline\":1893456000"));
    }

    @Test
    void missionDeadlineHelpers() {
        Instant now = Instant.ofEpochSecond(1_000_000);
        Mission past = new Mission("m", "t", "d", null, null, null,
                Instant.ofEpochSecond(999_999), MissionStatus.OPEN, null, null);
        Mission future = new Mission("m", "t", "d", null, null, null,
                Instant.ofEpochSecond(1_000_001), MissionStatus.OPEN, null, null);
        assertTrue(past.isPastDeadline(now));
        assertFalse(future.isPastDeadline(now));
        // a null deadline is never past-deadline
        Mission noDeadline = new Mission("m", "t", "d", null, null, null,
                null, MissionStatus.OPEN, null, null);
        assertFalse(noDeadline.isPastDeadline(now));
        assertTrue(noDeadline.submissions().isEmpty());
    }
}
