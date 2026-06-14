package org.aigen.oabp

import io.ktor.client.engine.mock.MockEngine
import io.ktor.client.engine.mock.MockRequestHandleScope
import io.ktor.client.engine.mock.respond
import io.ktor.client.request.HttpRequestData
import io.ktor.client.request.HttpResponseData
import io.ktor.http.HttpHeaders
import io.ktor.http.HttpMethod
import io.ktor.http.HttpStatusCode
import io.ktor.http.content.OutgoingContent
import io.ktor.http.headersOf
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.aigen.oabp.a2a.Message
import org.aigen.oabp.model.CreateMissionRequest
import org.aigen.oabp.model.Currency
import org.aigen.oabp.model.MissionStatus
import org.aigen.oabp.model.VerificationType
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNotNull
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.io.IOException
import java.math.BigDecimal
import java.time.Instant

/**
 * End-to-end tests for [OabpClient] driven by a Ktor [MockEngine], verifying both the
 * requests the client emits and how it decodes responses.
 */
class OabpClientTest {
    private val jsonHeaders = headersOf(HttpHeaders.ContentType, "application/json")

    /** Builds a client over a [MockEngine] replying via [handler], capturing requests into [captured]. */
    private fun client(
        captured: MutableList<HttpRequestData> = mutableListOf(),
        handler: MockRequestHandleScope.(HttpRequestData) -> HttpResponseData,
    ): OabpClient {
        val engine =
            MockEngine { request ->
                captured.add(request)
                handler(request)
            }
        return OabpClient(OabpClient.Config(baseUrl = "https://oabp.test"), engine)
    }

    /** Asserts that [block] throws [T], returning the caught exception. Works with suspend. */
    private suspend inline fun <reified T : Throwable> assertSuspendThrows(block: () -> Unit): T {
        try {
            block()
        } catch (t: Throwable) {
            if (t is T) return t
            throw AssertionError("Expected ${T::class.simpleName} but got ${t::class.simpleName}: ${t.message}", t)
        }
        throw AssertionError("Expected ${T::class.simpleName} but nothing was thrown")
    }

    private fun HttpRequestData.bodyText(): String =
        when (val content = this.body) {
            is OutgoingContent.ByteArrayContent -> String(content.bytes())
            else -> ""
        }

    private fun String.asJsonObject(): JsonObject = Json.parseToJsonElement(this).jsonObject

    @Test
    fun listMissions_parsesArrayAndHitsCorrectPath() =
        runTest {
            val captured = mutableListOf<HttpRequestData>()
            val payload =
                """
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
                """.trimIndent()
            client(captured) { respond(payload, HttpStatusCode.OK, jsonHeaders) }.use {
                val missions = it.listMissions()

                assertEquals(2, missions.size)
                val m1 = missions[0]
                assertEquals("m1", m1.id)
                assertEquals(Currency.AIGEN, m1.reward!!.currency)
                assertEquals(0, BigDecimal("100").compareTo(m1.reward!!.amount))
                assertEquals(VerificationType.FirstValidMatch, m1.verificationType)
                assertEquals("0x[a-fA-F0-9]{64}", m1.verificationParams.regex)
                assertTrue(m1.isOpen)
                assertEquals(Instant.ofEpochSecond(1_893_456_000L), m1.deadline)

                val m2 = missions[1]
                assertEquals(Currency.USDC, m2.reward!!.currency)
                assertEquals(VerificationType.Oracle, m2.verificationType)
                assertEquals("GoPlus token-security", m2.verificationParams.oracleDescription)

                val req = captured.single()
                assertEquals(HttpMethod.Get, req.method)
                assertEquals("https://oabp.test/api/missions", req.url.toString())
                assertEquals("application/json", req.headers[HttpHeaders.Accept])
                assertTrue(req.headers[HttpHeaders.UserAgent]!!.startsWith("oabp-kotlin-sdk/"))
            }
        }

    @Test
    fun getMission_parsesDetailWithSubmissionsAndResolution() =
        runTest {
            val captured = mutableListOf<HttpRequestData>()
            val payload =
                """
                {
                  "id": "m42",
                  "title": "Deliver repo",
                  "description": "Ship a Go CLI",
                  "reward": {"amount": 1000, "currency": "USDC"},
                  "verification_type": "oracle",
                  "verification_params": {"oracle_description": "GitHub repo deliverable"},
                  "deadline": 1893456000,
                  "status": "resolved",
                  "submissions": [
                    {"id": "s1", "submitter_agent_id": "a9", "proof": "https://github.com/x/y",
                     "accepted": true, "submitted_at": 1893450000}
                  ],
                  "resolution": {
                    "winner_agent_id": "a9",
                    "winning_submission_id": "s1",
                    "oracle_verdict": "repo exists, non-empty, Go",
                    "resolved_at": 1893455000
                  }
                }
                """.trimIndent()
            client(captured) { respond(payload, HttpStatusCode.OK, jsonHeaders) }.use {
                val m = it.getMission("m42")
                assertEquals("m42", m.id)
                assertEquals(MissionStatus.RESOLVED, m.status)
                assertTrue(m.status.isTerminal)
                assertEquals(1, m.submissions.size)
                assertTrue(m.submissions[0].isAccepted)
                assertEquals(Instant.ofEpochSecond(1_893_450_000L), m.submissions[0].submittedAt)
                assertNotNull(m.resolution)
                assertTrue(m.resolution!!.hasWinner)
                assertEquals("a9", m.resolution!!.winnerAgentId)
                assertEquals("repo exists, non-empty, Go", m.resolution!!.oracleVerdict)

                assertEquals("https://oabp.test/api/missions/m42", captured.single().url.toString())
            }
        }

    @Test
    fun getMission_encodesPathSegment() =
        runTest {
            val captured = mutableListOf<HttpRequestData>()
            client(captured) { respond("""{"id":"a b/c"}""", HttpStatusCode.OK, jsonHeaders) }.use {
                it.getMission("a b/c")
                // Space and slash must be percent-encoded into a single path segment.
                assertEquals("https://oabp.test/api/missions/a%20b%2Fc", captured.single().url.toString())
            }
        }

    @Test
    fun createMission_sendsCorrectWireBody() =
        runTest {
            val captured = mutableListOf<HttpRequestData>()
            client(captured) {
                respond(
                    """{"id":"new1","status":"open","verification_type":"first_valid_match"}""",
                    HttpStatusCode.Created,
                    jsonHeaders,
                )
            }.use {
                val created =
                    it.createMission(
                        CreateMissionRequest.firstValidMatch(
                            creatorAgentId = "creator-1",
                            title = "Match the flag",
                            description = "Submit the secret",
                            rewardAmount = 100,
                            rewardCurrency = Currency.AIGEN,
                            regex = "FLAG\\{.*\\}",
                            deadlineHours = 24,
                        ),
                    )
                assertEquals("new1", created.id)
                assertEquals(MissionStatus.OPEN, created.status)

                val req = captured.single()
                assertEquals(HttpMethod.Post, req.method)
                assertEquals("https://oabp.test/api/missions", req.url.toString())
                assertEquals("application/json", req.headers[HttpHeaders.Accept])

                val sent = req.bodyText().asJsonObject()
                assertEquals("creator-1", sent["creator_agent_id"]!!.jsonPrimitive.content)
                assertEquals("Match the flag", sent["title"]!!.jsonPrimitive.content)
                assertEquals("AIGEN", sent["reward_currency"]!!.jsonPrimitive.content)
                assertEquals("first_valid_match", sent["verification_type"]!!.jsonPrimitive.content)
                assertEquals(24, sent["deadline_hours"]!!.jsonPrimitive.content.toInt())
                // BigDecimal serializes as a bare JSON number with full precision.
                assertEquals("100", sent["reward_amount"]!!.jsonPrimitive.content)
                assertEquals(
                    "FLAG\\{.*\\}",
                    sent["verification_params"]!!.jsonObject["regex"]!!.jsonPrimitive.content,
                )
            }
        }

    @Test
    fun submit_postsBodyToSubmitPath() =
        runTest {
            val captured = mutableListOf<HttpRequestData>()
            client(captured) {
                respond(
                    """{"submission_id":"sub-7","mission_id":"m1","accepted":true,"status":"accepted"}""",
                    HttpStatusCode.OK,
                    jsonHeaders,
                )
            }.use {
                val receipt = it.submit("m1", "agent-99", "https://github.com/me/poc")
                assertEquals("sub-7", receipt.submissionId)
                assertTrue(receipt.isAccepted)
                assertEquals("accepted", receipt.status)

                val req = captured.single()
                assertEquals(HttpMethod.Post, req.method)
                assertEquals("https://oabp.test/missions/m1/submit", req.url.toString())
                val sent = req.bodyText().asJsonObject()
                assertEquals("agent-99", sent["submitter_agent_id"]!!.jsonPrimitive.content)
                assertEquals("https://github.com/me/poc", sent["proof"]!!.jsonPrimitive.content)
            }
        }

    @Test
    fun getStats_parsesCounters() =
        runTest {
            client {
                respond(
                    """{"resolved":12,"open":5,"lifetime_reward_aigen_paid":108000.5}""",
                    HttpStatusCode.OK,
                    jsonHeaders,
                )
            }.use {
                val stats = it.getStats()
                assertEquals(12, stats.resolved)
                assertEquals(5, stats.open)
                assertEquals(17, stats.total)
                assertEquals(0, BigDecimal("108000.5").compareTo(stats.lifetimeRewardAigenPaid))
            }
        }

    @Test
    fun a2a_sendMessage_buildsRpcEnvelopeAndDecodesResult() =
        runTest {
            val captured = mutableListOf<HttpRequestData>()
            client(captured) {
                respond(
                    """{"jsonrpc":"2.0","id":"x","result":{"taskId":"t-1","status":"completed"}}""",
                    HttpStatusCode.OK,
                    jsonHeaders,
                )
            }.use {
                val resp = it.sendMessage(Message.userText("list open missions"))
                assertFalse(resp.isError)
                assertNotNull(resp.result)
                assertEquals("t-1", resp.result!!.jsonObject["taskId"]!!.jsonPrimitive.content)

                val req = captured.single()
                assertEquals("https://oabp.test/api/a2a", req.url.toString())
                val sent = req.bodyText().asJsonObject()
                assertEquals("2.0", sent["jsonrpc"]!!.jsonPrimitive.content)
                assertEquals("message/send", sent["method"]!!.jsonPrimitive.content)
                assertNotNull(sent["id"])
                val msg = sent["params"]!!.jsonObject["message"]!!.jsonObject
                assertEquals("user", msg["role"]!!.jsonPrimitive.content)
                val firstPart = (msg["parts"] as JsonArray)[0].jsonObject
                assertEquals("text", firstPart["kind"]!!.jsonPrimitive.content)
                assertEquals("list open missions", firstPart["text"]!!.jsonPrimitive.content)
            }
        }

    @Test
    fun a2a_tasksGet_and_tasksList_useExpectedMethods() =
        runTest {
            val captured = mutableListOf<HttpRequestData>()
            client(captured) {
                respond("""{"jsonrpc":"2.0","id":"x","result":[]}""", HttpStatusCode.OK, jsonHeaders)
            }.use {
                it.getTask("t-9")
                it.listTasks()
                val getBody = captured[0].bodyText().asJsonObject()
                assertEquals("tasks/get", getBody["method"]!!.jsonPrimitive.content)
                assertEquals("t-9", getBody["params"]!!.jsonObject["id"]!!.jsonPrimitive.content)
                val listBody = captured[1].bodyText().asJsonObject()
                assertEquals("tasks/list", listBody["method"]!!.jsonPrimitive.content)
                // tasks/list has no params -> omitted by explicitNulls=false
                assertNull(listBody["params"])
            }
        }

    @Test
    fun a2a_jsonRpcErrorIsReturnedNotThrown() =
        runTest {
            client {
                respond(
                    """{"jsonrpc":"2.0","id":"x","error":{"code":-32601,"message":"Method not found"}}""",
                    HttpStatusCode.OK,
                    jsonHeaders,
                )
            }.use {
                val resp = it.a2a("does/notExist")
                assertTrue(resp.isError)
                assertEquals(-32601, resp.error!!.code)
                assertEquals("Method not found", resp.error!!.message)
                // a2aResultAs must surface the error rather than return a value.
                val ex = assertSuspendThrows<IllegalStateException> { it.a2aResultAs<JsonObject>(resp) }
                assertTrue(ex.message!!.contains("error"))
            }
        }

    @Test
    fun apiError_mapsToApiExceptionWithStatusAndBody() =
        runTest {
            client { respond("""{"error":"not found"}""", HttpStatusCode.NotFound, jsonHeaders) }.use {
                val ex = assertSuspendThrows<OabpApiException> { it.getMission("nope") }
                assertEquals(404, ex.statusCode)
                assertTrue(ex.isNotFound)
                assertTrue(ex.isClientError)
                assertTrue(ex.body.contains("not found"))
            }
        }

    @Test
    fun serverError_500_isApiException() =
        runTest {
            client { respond("boom", HttpStatusCode.InternalServerError, jsonHeaders) }.use {
                val ex = assertSuspendThrows<OabpApiException> { it.listMissions() }
                assertEquals(500, ex.statusCode)
                assertTrue(ex.isServerError)
            }
        }

    @Test
    fun transportFailure_mapsToTransportException() =
        runTest {
            val engine = MockEngine { throw IOException("connection refused") }
            OabpClient(OabpClient.Config(baseUrl = "https://oabp.test"), engine).use {
                val ex = assertSuspendThrows<OabpTransportException> { it.getStats() }
                assertTrue(ex.message!!.contains("transport", ignoreCase = true))
            }
        }

    @Test
    fun forwardCompat_unknownEnumAndVerificationTypeDoNotThrow() =
        runTest {
            val payload =
                """
                [{
                  "id":"mX","title":"future","description":"d",
                  "reward":{"amount":1,"currency":"BTC"},
                  "verification_type":"zk_proof",
                  "status":"archived",
                  "submissions":[]
                }]
                """.trimIndent()
            client { respond(payload, HttpStatusCode.OK, jsonHeaders) }.use {
                val m = it.listMissions().single()
                assertEquals(Currency.UNKNOWN, m.reward!!.currency)
                assertEquals(MissionStatus.UNKNOWN, m.status)
                val vt = m.verificationType
                assertTrue(vt is VerificationType.Unknown)
                assertEquals("zk_proof", (vt as VerificationType.Unknown).wire)
            }
        }

    @Test
    fun decodeFailure_mapsToSerializationException() =
        runTest {
            // Valid JSON but wrong shape (missing required `id`) -> serialization error.
            client { respond("""{"title":"no id"}""", HttpStatusCode.OK, jsonHeaders) }.use {
                assertSuspendThrows<OabpSerializationException> { it.getMission("m") }
            }
        }
}
