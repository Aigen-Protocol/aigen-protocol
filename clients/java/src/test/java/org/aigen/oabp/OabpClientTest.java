package org.aigen.oabp;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import okhttp3.mockwebserver.RecordedRequest;
import org.aigen.oabp.a2a.JsonRpcResponse;
import org.aigen.oabp.a2a.Message;
import org.aigen.oabp.model.CreateMissionRequest;
import org.aigen.oabp.model.Currency;
import org.aigen.oabp.model.Mission;
import org.aigen.oabp.model.MissionStatus;
import org.aigen.oabp.model.ProtocolStats;
import org.aigen.oabp.model.Submission;
import org.aigen.oabp.model.SubmissionReceipt;
import org.aigen.oabp.model.VerificationType;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * End-to-end tests for {@link OabpClient} driven by an in-process {@link MockWebServer},
 * verifying both the requests the client emits and how it binds responses.
 */
class OabpClientTest {

    private MockWebServer server;
    private OabpClient client;
    private final ObjectMapper mapper = Json.newMapper();

    @BeforeEach
    void setUp() throws Exception {
        server = new MockWebServer();
        server.start();
        client = OabpClient.builder()
                .baseUrl(server.url("/").toString())
                .build();
    }

    @AfterEach
    void tearDown() throws Exception {
        client.close();
        server.shutdown();
    }

    @Test
    void listMissions_parsesArrayAndHitsCorrectPath() throws Exception {
        String json = """
                [
                  {
                    "id": "m1",
                    "title": "Find a bug",
                    "description": "Audit contract X",
                    "reward": {"amount": 100, "currency": "AIGEN"},
                    "verification_type": "first_valid_match",
                    "verification_params": {"regex": "0x[a-fA-F0-9]{64}"},
                    "deadline": 1893456000,
                    "status": "open",
                    "submissions": []
                  },
                  {
                    "id": "m2",
                    "title": "Safety review",
                    "description": "GoPlus review of token",
                    "reward": {"amount": 50.5, "currency": "USDC"},
                    "verification_type": "oracle",
                    "verification_params": {"oracle_description": "GoPlus token-security"},
                    "deadline": 1893456000,
                    "status": "open",
                    "submissions": []
                  }
                ]
                """;
        server.enqueue(new MockResponse()
                .setHeader("Content-Type", "application/json")
                .setBody(json));

        List<Mission> missions = client.listMissions();

        assertEquals(2, missions.size());
        Mission m1 = missions.get(0);
        assertEquals("m1", m1.id());
        assertEquals(Currency.AIGEN, m1.reward().currency());
        assertEquals(0, new BigDecimal("100").compareTo(m1.reward().amount()));
        assertEquals(VerificationType.FIRST_VALID_MATCH, m1.verificationType());
        assertEquals("0x[a-fA-F0-9]{64}", m1.verificationParams().regexOpt().orElseThrow());
        assertTrue(m1.isOpen());
        assertEquals(Instant.ofEpochSecond(1893456000L), m1.deadlineOpt().orElseThrow());

        Mission m2 = missions.get(1);
        assertEquals(Currency.USDC, m2.reward().currency());
        assertEquals(VerificationType.ORACLE, m2.verificationType());
        assertEquals("GoPlus token-security",
                m2.verificationParams().oracleDescriptionOpt().orElseThrow());

        RecordedRequest recorded = server.takeRequest();
        assertEquals("GET", recorded.getMethod());
        assertEquals("/api/missions", recorded.getPath());
        assertEquals("application/json", recorded.getHeader("Accept"));
        assertTrue(recorded.getHeader("User-Agent").startsWith("oabp-java-sdk/"));
    }

    @Test
    void getMission_parsesDetailWithSubmissionsAndResolution() throws Exception {
        String json = """
                {
                  "id": "m42",
                  "title": "Deliver repo",
                  "description": "Build a Go CLI",
                  "reward": {"amount": 1000, "currency": "AIGEN"},
                  "verification_type": "oracle",
                  "verification_params": {"oracle_description": "GitHub repo deliverable"},
                  "deadline": 1900000000,
                  "status": "resolved",
                  "submissions": [
                    {"id": "s1", "submitter_agent_id": "agentA",
                     "proof": "https://github.com/a/b", "accepted": true, "submitted_at": 1899999000}
                  ],
                  "resolution": {
                    "winner_agent_id": "agentA",
                    "winning_submission_id": "s1",
                    "oracle_verdict": "repo exists, non-empty, language=Go",
                    "resolved_at": 1899999500
                  }
                }
                """;
        server.enqueue(new MockResponse().setBody(json));

        Mission m = client.getMission("m42");

        assertEquals("m42", m.id());
        assertEquals(MissionStatus.RESOLVED, m.status());
        assertTrue(m.status().isTerminal());
        assertEquals(1, m.submissions().size());
        Submission s = m.submissions().get(0);
        assertEquals("agentA", s.submitterAgentId());
        assertTrue(s.isAccepted());
        assertEquals(Instant.ofEpochSecond(1899999000L), s.submittedAtOpt().orElseThrow());

        assertTrue(m.resolutionOpt().isPresent());
        assertTrue(m.resolutionOpt().orElseThrow().hasWinner());
        assertEquals("agentA", m.resolutionOpt().orElseThrow().winnerAgentId());
        assertEquals("repo exists, non-empty, language=Go",
                m.resolutionOpt().orElseThrow().oracleVerdictOpt().orElseThrow());

        RecordedRequest recorded = server.takeRequest();
        assertEquals("GET", recorded.getMethod());
        assertEquals("/api/missions/m42", recorded.getPath());
    }

    @Test
    void submissionsListIsImmutable() throws Exception {
        server.enqueue(new MockResponse().setBody("""
                {"id":"m1","title":"t","description":"d",
                 "reward":{"amount":1,"currency":"AIGEN"},
                 "verification_type":"first_valid_match","verification_params":{},
                 "deadline":1,"status":"open","submissions":[]}
                """));
        Mission m = client.getMission("m1");
        assertThrows(UnsupportedOperationException.class,
                () -> m.submissions().add(null));
    }

    @Test
    void createMission_sendsCorrectBodyShapeAndParsesResult() throws Exception {
        server.enqueue(new MockResponse().setBody("""
                {"id":"new1","title":"Audit token X","description":"desc",
                 "reward":{"amount":250,"currency":"AIGEN"},
                 "verification_type":"oracle",
                 "verification_params":{"oracle_description":"GoPlus review of 0xabc"},
                 "deadline":1893456000,"status":"open","submissions":[]}
                """));

        CreateMissionRequest req = CreateMissionRequest.builder()
                .creatorAgentId("agent-123")
                .title("Audit token X")
                .description("Run a GoPlus safety review and report findings.")
                .rewardAmount(250).aigen()
                .oracleDescription("GoPlus review of 0xabc")
                .deadlineHours(48)
                .build();

        Mission created = client.createMission(req);
        assertEquals("new1", created.id());

        RecordedRequest recorded = server.takeRequest();
        assertEquals("POST", recorded.getMethod());
        assertEquals("/api/missions", recorded.getPath());
        assertEquals("application/json", recorded.getHeader("Content-Type"));

        JsonNode body = mapper.readTree(recorded.getBody().readUtf8());
        assertEquals("agent-123", body.get("creator_agent_id").asText());
        assertEquals("Audit token X", body.get("title").asText());
        assertEquals(250, body.get("reward_amount").asInt());
        assertEquals("AIGEN", body.get("reward_currency").asText());
        assertEquals("oracle", body.get("verification_type").asText());
        assertEquals("GoPlus review of 0xabc",
                body.get("verification_params").get("oracle_description").asText());
        assertEquals(48, body.get("deadline_hours").asInt());
        // Default-null verification fields must be omitted (NON_NULL), not sent as null.
        assertFalse(body.get("verification_params").has("regex"));
    }

    @Test
    void createMission_firstValidMatchBodyCarriesRegex() throws Exception {
        server.enqueue(new MockResponse().setBody("""
                {"id":"r1","title":"t","description":"d",
                 "reward":{"amount":10,"currency":"USDC"},
                 "verification_type":"first_valid_match",
                 "verification_params":{"regex":"^done$"},
                 "deadline":1,"status":"open","submissions":[]}
                """));

        CreateMissionRequest req = CreateMissionRequest.builder()
                .creatorAgentId("creator")
                .title("t")
                .description("d")
                .rewardAmount("10.00").usdc()
                .regex("^done$")            // also defaults verificationType to FIRST_VALID_MATCH
                .deadlineHours(12)
                .build();
        assertEquals(VerificationType.FIRST_VALID_MATCH, req.verificationType());

        client.createMission(req);

        JsonNode body = mapper.readTree(server.takeRequest().getBody().readUtf8());
        assertEquals("first_valid_match", body.get("verification_type").asText());
        assertEquals("^done$", body.get("verification_params").get("regex").asText());
        assertEquals("USDC", body.get("reward_currency").asText());
    }

    @Test
    void submit_sendsBodyToSubmitPathAndParsesReceipt() throws Exception {
        server.enqueue(new MockResponse().setBody("""
                {"submission_id":"sub-9","mission_id":"m1","accepted":true,
                 "status":"accepted","message":"matched regex"}
                """));

        SubmissionReceipt receipt = client.submit("m1", "agent-999", "https://example.com/proof");

        assertEquals("sub-9", receipt.submissionId());
        assertTrue(receipt.isAccepted());
        assertEquals("accepted", receipt.statusOpt().orElseThrow());

        RecordedRequest recorded = server.takeRequest();
        assertEquals("POST", recorded.getMethod());
        assertEquals("/missions/m1/submit", recorded.getPath());
        JsonNode body = mapper.readTree(recorded.getBody().readUtf8());
        assertEquals("agent-999", body.get("submitter_agent_id").asText());
        assertEquals("https://example.com/proof", body.get("proof").asText());
    }

    @Test
    void getStats_parsesCounters() throws Exception {
        server.enqueue(new MockResponse().setBody(
                "{\"resolved\":12,\"open\":5,\"lifetime_reward_aigen_paid\":108000.5}"));

        ProtocolStats stats = client.getStats();
        assertEquals(12, stats.resolved());
        assertEquals(5, stats.open());
        assertEquals(17, stats.total());
        assertEquals(0, new BigDecimal("108000.5").compareTo(stats.lifetimeRewardAigenPaid()));

        assertEquals("/api/stats", server.takeRequest().getPath());
    }

    @Test
    void a2a_sendMessage_buildsJsonRpcEnvelope() throws Exception {
        server.enqueue(new MockResponse().setBody("""
                {"jsonrpc":"2.0","id":"x","result":{"id":"task-1","status":{"state":"completed"}}}
                """));

        JsonRpcResponse resp = client.sendMessage(Message.userText("hello agent"));
        assertFalse(resp.isError());
        assertEquals("2.0", resp.jsonrpc());
        assertTrue(resp.resultOpt().isPresent());

        RecordedRequest recorded = server.takeRequest();
        assertEquals("POST", recorded.getMethod());
        assertEquals("/api/a2a", recorded.getPath());
        JsonNode body = mapper.readTree(recorded.getBody().readUtf8());
        assertEquals("2.0", body.get("jsonrpc").asText());
        assertEquals("message/send", body.get("method").asText());
        assertNotNull(body.get("id"));
        assertEquals("user", body.get("params").get("message").get("role").asText());
        assertEquals("hello agent",
                body.get("params").get("message").get("parts").get(0).get("text").asText());
        assertEquals("text",
                body.get("params").get("message").get("parts").get(0).get("kind").asText());
    }

    @Test
    void a2a_resultBinding_andErrorPropagation() throws Exception {
        // First: a successful result we bind to a record.
        server.enqueue(new MockResponse().setBody("""
                {"jsonrpc":"2.0","id":"x","result":{"id":"task-7","state":"working"}}
                """));
        JsonRpcResponse ok = client.getTask("task-7");
        TaskView view = client.a2aResultAs(ok, TaskView.class);
        assertEquals("task-7", view.id());
        assertEquals("working", view.state());
        JsonNode getBody = mapper.readTree(server.takeRequest().getBody().readUtf8());
        assertEquals("tasks/get", getBody.get("method").asText());
        assertEquals("task-7", getBody.get("params").get("id").asText());

        // Second: a JSON-RPC error is returned (not thrown) but binding it throws.
        server.enqueue(new MockResponse().setBody("""
                {"jsonrpc":"2.0","id":"y","error":{"code":-32601,"message":"Method not found"}}
                """));
        JsonRpcResponse err = client.listTasks();
        assertTrue(err.isError());
        assertEquals(-32601, err.errorOpt().orElseThrow().code());
        OabpException ex = assertThrows(OabpException.class,
                () -> client.a2aResultAs(err, TaskView.class));
        assertTrue(ex.getMessage().contains("error"));
    }

    @Test
    void apiException_carriesStatusAndBody_on404() throws Exception {
        server.enqueue(new MockResponse()
                .setResponseCode(404)
                .setBody("{\"error\":\"mission not found\"}"));

        OabpException.ApiException ex = assertThrows(OabpException.ApiException.class,
                () -> client.getMission("does-not-exist"));
        assertEquals(404, ex.statusCode());
        assertTrue(ex.isNotFound());
        assertTrue(ex.isClientError());
        assertFalse(ex.isServerError());
        assertTrue(ex.body().contains("mission not found"));
    }

    @Test
    void apiException_on500_isServerError() throws Exception {
        server.enqueue(new MockResponse().setResponseCode(503).setBody("upstream down"));
        OabpException.ApiException ex = assertThrows(OabpException.ApiException.class,
                client::listMissions);
        assertEquals(503, ex.statusCode());
        assertTrue(ex.isServerError());
    }

    @Test
    void malformedJson_raisesOabpException_notApiException() throws Exception {
        server.enqueue(new MockResponse().setBody("not-json-at-all{"));
        OabpException ex = assertThrows(OabpException.class, client::listMissions);
        assertFalse(ex instanceof OabpException.ApiException);
        assertTrue(ex.getMessage().toLowerCase().contains("parse"));
    }

    @Test
    void unknownEnumValuesDegradeToUnknown_forwardCompatible() throws Exception {
        server.enqueue(new MockResponse().setBody("""
                {"id":"mX","title":"t","description":"d",
                 "reward":{"amount":1,"currency":"DOGE"},
                 "verification_type":"zk_proof","verification_params":{},
                 "deadline":1,"status":"quantum","submissions":[]}
                """));
        Mission m = client.getMission("mX");
        assertEquals(Currency.UNKNOWN, m.reward().currency());
        assertEquals(VerificationType.UNKNOWN, m.verificationType());
        assertEquals(MissionStatus.UNKNOWN, m.status());
    }

    @Test
    void baseUrlTrailingSlashesAreNormalized() throws Exception {
        try (OabpClient c = OabpClient.create(server.url("/").toString() + "///")) {
            server.enqueue(new MockResponse().setBody("[]"));
            assertTrue(c.listMissions().isEmpty());
            assertEquals("/api/missions", server.takeRequest().getPath());
        }
    }

    @Test
    void customObjectMapperIsUsed() {
        ObjectMapper custom = Json.newMapper();
        OabpClient c = OabpClient.builder().objectMapper(custom).build();
        assertSame(custom, c.objectMapper());
    }

    /** Minimal A2A task projection used to exercise {@link OabpClient#a2aResultAs}. */
    record TaskView(String id, String state) {
    }
}
