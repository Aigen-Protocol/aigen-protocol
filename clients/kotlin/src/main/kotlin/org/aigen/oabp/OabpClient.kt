package org.aigen.oabp

import io.ktor.client.HttpClient
import io.ktor.client.HttpClientConfig
import io.ktor.client.call.body
import io.ktor.client.engine.HttpClientEngine
import io.ktor.client.engine.cio.CIO
import io.ktor.client.plugins.HttpResponseValidator
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.defaultRequest
import io.ktor.client.request.get
import io.ktor.client.request.header
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.client.statement.HttpResponse
import io.ktor.client.statement.bodyAsText
import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.http.contentType
import io.ktor.http.encodeURLPathPart
import io.ktor.http.isSuccess
import io.ktor.serialization.JsonConvertException
import io.ktor.serialization.kotlinx.json.json
import io.ktor.util.appendIfNameAbsent
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.encodeToJsonElement
import org.aigen.oabp.a2a.AgentCard
import org.aigen.oabp.a2a.JsonRpcRequest
import org.aigen.oabp.a2a.JsonRpcResponse
import org.aigen.oabp.a2a.Message
import org.aigen.oabp.model.CreateMissionRequest
import org.aigen.oabp.model.Mission
import org.aigen.oabp.model.ProtocolStats
import org.aigen.oabp.model.SubmissionReceipt
import org.aigen.oabp.model.SubmitRequest
import java.io.Closeable
import java.util.UUID

/**
 * Coroutine client for the OABP / AIGEN agent-bounty protocol.
 *
 * Built on a Ktor [HttpClient] with kotlinx.serialization. Every endpoint is exposed as a
 * `suspend` function that returns a `@Serializable` data class and throws an [OabpException]
 * subtype on failure (transport / serialization / non-2xx API). The client is safe to share
 * across coroutines; create one and reuse it.
 *
 * ```kotlin
 * OabpClient().use { client ->
 *     val open: List<Mission> = client.listMissions()
 *
 *     val created = client.createMission(
 *         CreateMissionRequest.oracle(
 *             creatorAgentId = "agent-123",
 *             title = "Audit token X",
 *             description = "Run a GoPlus safety review and report findings.",
 *             rewardAmount = 250,
 *             rewardCurrency = Currency.AIGEN,
 *             oracleDescription = "GoPlus token-security review of 0xabc...",
 *             deadlineHours = 48,
 *         ),
 *     )
 *
 *     val receipt = client.submit(created.id, "agent-999", "https://github.com/me/report")
 * }
 * ```
 *
 * `AIGEN` is the protocol's uncapped, off-chain reputation token; verification is
 * permissionless (content-addressed first-valid-match, or oracle-backed via GoPlus /
 * GitHub). A 0.5% protocol fee applies to rewards.
 *
 * @param config immutable configuration (base URL, timeouts, user agent).
 * @param engine the Ktor engine to drive requests; defaults to [CIO]. Pass a
 *   `MockEngine` to test without a network.
 */
public class OabpClient(
    config: Config = Config(),
    engine: HttpClientEngine? = null,
) : Closeable {
    /**
     * Immutable configuration for an [OabpClient].
     *
     * @property baseUrl the protocol base URL (trailing slashes are stripped).
     * @property requestTimeoutMillis per-request timeout applied to every call.
     * @property connectTimeoutMillis TCP connect timeout.
     * @property userAgent the `User-Agent` header sent with every request.
     */
    public data class Config(
        val baseUrl: String = DEFAULT_BASE_URL,
        val requestTimeoutMillis: Long = 30_000,
        val connectTimeoutMillis: Long = 10_000,
        val userAgent: String = USER_AGENT,
    ) {
        init {
            require(baseUrl.isNotBlank()) { "baseUrl must not be blank" }
        }
    }

    private val baseUrl: String = config.baseUrl.trimEnd('/')
    private val userAgent: String = config.userAgent
    private val http: HttpClient = buildClient(config, engine)

    /**
     * Lists all currently open missions (`GET /api/missions`).
     *
     * @return the open missions; never `null` (empty when there are none).
     * @throws OabpApiException on a non-2xx status.
     * @throws OabpSerializationException if the body cannot be parsed.
     * @throws OabpTransportException on a transport failure.
     */
    public suspend fun listMissions(): List<Mission> = get("/api/missions")

    /**
     * Fetches one mission by id, including its submissions and resolution
     * (`GET /api/missions/{id}`).
     *
     * @param missionId the mission id (required, non-blank).
     * @throws OabpApiException with [OabpApiException.isNotFound] `true` if no such mission.
     * @throws OabpSerializationException if the body cannot be parsed.
     * @throws OabpTransportException on a transport failure.
     */
    public suspend fun getMission(missionId: String): Mission {
        requireId(missionId, "missionId")
        return get("/api/missions/${missionId.encodeURLPathPart()}")
    }

    /**
     * Creates a new mission (`POST /api/missions`).
     *
     * @param request the validated mission request (build via the
     *   [CreateMissionRequest.firstValidMatch] / [CreateMissionRequest.oracle] factories).
     * @return the created mission.
     * @throws OabpApiException on a non-2xx status.
     * @throws OabpSerializationException if the body cannot be parsed.
     * @throws OabpTransportException on a transport failure.
     */
    public suspend fun createMission(request: CreateMissionRequest): Mission = post("/api/missions", request)

    /**
     * Submits a deliverable to a mission (`POST /missions/{id}/submit`).
     *
     * @param missionId the target mission id (required).
     * @param submitterAgentId the submitting agent's id (required).
     * @param proof the deliverable proof — free text or a URL (required).
     * @return the server's submission receipt.
     * @throws OabpApiException on a non-2xx status.
     * @throws OabpSerializationException if the body cannot be parsed.
     * @throws OabpTransportException on a transport failure.
     */
    public suspend fun submit(
        missionId: String,
        submitterAgentId: String,
        proof: String,
    ): SubmissionReceipt = submit(missionId, SubmitRequest(submitterAgentId, proof))

    /**
     * Submits a deliverable using a prebuilt [SubmitRequest].
     *
     * @param missionId the target mission id (required).
     * @param request the submit body (required).
     * @return the server's submission receipt.
     */
    public suspend fun submit(
        missionId: String,
        request: SubmitRequest,
    ): SubmissionReceipt {
        requireId(missionId, "missionId")
        return post("/missions/${missionId.encodeURLPathPart()}/submit", request)
    }

    /**
     * Fetches aggregate protocol statistics (`GET /api/stats`).
     *
     * @return resolved/open counts and lifetime AIGEN paid.
     */
    public suspend fun getStats(): ProtocolStats = get("/api/stats")

    // ------------------------------------------------------------------
    // A2A JSON-RPC
    // ------------------------------------------------------------------

    /**
     * Performs a raw A2A JSON-RPC 2.0 call against `POST /api/a2a`.
     *
     * A non-2xx HTTP status raises [OabpApiException]; a JSON-RPC-level `error` is returned
     * in the [JsonRpcResponse] (not thrown), so the caller can inspect the code. Use
     * [a2aResultAs] to decode a successful result.
     *
     * @param method the RPC method (e.g. `"message/send"`, `"tasks/get"`, `"tasks/list"`).
     * @param params the method parameters as a [JsonElement], or `null`.
     * @return the JSON-RPC response envelope.
     */
    public suspend fun a2a(
        method: String,
        params: JsonElement? = null,
    ): JsonRpcResponse {
        require(method.isNotBlank()) { "method is required" }
        val rpc = JsonRpcRequest(id = UUID.randomUUID().toString(), method = method, params = params)
        return post("/api/a2a", rpc)
    }

    /**
     * Sends an A2A message to the protocol agent via the `message/send` method.
     *
     * @param message the message to send.
     * @return the JSON-RPC response (typically a task result).
     */
    public suspend fun sendMessage(message: Message): JsonRpcResponse {
        val params = OabpJson.encodeToJsonElement(MessageParams(message))
        return a2a("message/send", params)
    }

    /**
     * Convenience: sends a single user-text A2A message via `message/send`.
     *
     * @param text the user message text.
     */
    public suspend fun sendText(text: String): JsonRpcResponse = sendMessage(Message.userText(text))

    /**
     * Fetches an A2A task by id via the `tasks/get` method.
     *
     * @param taskId the task id.
     */
    public suspend fun getTask(taskId: String): JsonRpcResponse {
        requireId(taskId, "taskId")
        return a2a("tasks/get", OabpJson.encodeToJsonElement(IdParams(taskId)))
    }

    /** Lists A2A tasks via the `tasks/list` method. */
    public suspend fun listTasks(): JsonRpcResponse = a2a("tasks/list", null)

    /**
     * Decodes a successful JSON-RPC `result` into a concrete type [T].
     *
     * @throws OabpException if the response carried an `error`, had no `result`, or the
     *   result could not be decoded into [T].
     */
    public suspend inline fun <reified T> a2aResultAs(response: JsonRpcResponse): T {
        response.error?.let { error("A2A call returned error: code=${it.code} message=${it.message}") }
        val result = response.result
        if (result == null || result is JsonNull) {
            error("A2A response had no result to bind")
        }
        return OabpJson.decodeFromJsonElement(result)
    }

    /**
     * Fetches the protocol's well-known A2A agent card
     * (`GET /.well-known/agent-card.json`). The card is ES256-signed server-side; this
     * client returns the parsed (subset) card without verifying the signature.
     */
    public suspend fun getAgentCard(): AgentCard = get("/.well-known/agent-card.json")

    // ------------------------------------------------------------------
    // HTTP plumbing
    // ------------------------------------------------------------------

    private suspend inline fun <reified T> get(path: String): T {
        val response = execute { http.get(baseUrl + path) }
        return decode(response)
    }

    private suspend inline fun <reified T, reified B> post(
        path: String,
        body: B,
    ): T {
        val response =
            execute {
                http.post(baseUrl + path) {
                    contentType(ContentType.Application.Json)
                    setBody(body)
                }
            }
        return decode(response)
    }

    /** Runs the request, translating transport-level failures into [OabpTransportException]. */
    private suspend inline fun execute(block: () -> HttpResponse): HttpResponse =
        try {
            block()
        } catch (e: OabpException) {
            throw e
        } catch (e: kotlinx.coroutines.CancellationException) {
            throw e
        } catch (e: Throwable) {
            throw OabpTransportException("HTTP transport failure calling $baseUrl: ${e.message}", e)
        }

    /** Decodes a 2xx response body into [T], or throws [OabpApiException] / [OabpSerializationException]. */
    private suspend inline fun <reified T> decode(response: HttpResponse): T {
        if (!response.status.isSuccess()) {
            val raw = runCatching { response.bodyAsText() }.getOrDefault("")
            throw OabpApiException(
                statusCode = response.status.value,
                body = raw,
                message =
                    "OABP API returned HTTP ${response.status.value} for ${response.call.request.url}" +
                        if (raw.isBlank()) "" else ": ${raw.take(512)}",
            )
        }
        return try {
            response.body()
        } catch (e: JsonConvertException) {
            val raw = runCatching { response.bodyAsText() }.getOrDefault("")
            throw OabpSerializationException("Failed to parse OABP response: ${raw.take(512)}", e)
        }
    }

    /** Closes the underlying Ktor [HttpClient] and releases its resources. */
    override fun close() {
        http.close()
    }

    private fun buildClient(
        config: Config,
        engine: HttpClientEngine?,
    ): HttpClient {
        val configure: HttpClientConfig<*>.() -> Unit = {
            expectSuccess = false
            install(ContentNegotiation) {
                json(OabpJson)
            }
            install(HttpTimeout) {
                requestTimeoutMillis = config.requestTimeoutMillis
                connectTimeoutMillis = config.connectTimeoutMillis
            }
            defaultRequest {
                headers.appendIfNameAbsent(HttpHeaders.Accept, ContentType.Application.Json.toString())
                header(HttpHeaders.UserAgent, config.userAgent)
            }
            // Map low-level Ktor response exceptions (if any plugin re-enables expectSuccess)
            // onto our hierarchy; with expectSuccess=false this is largely a safety net.
            HttpResponseValidator {
                handleResponseExceptionWithRequest { cause, _ ->
                    if (cause is OabpException) throw cause
                }
            }
        }
        return if (engine != null) HttpClient(engine, configure) else HttpClient(CIO, configure)
    }

    public companion object {
        /** The protocol's public base URL. */
        public const val DEFAULT_BASE_URL: String = "https://cryptogenesis.duckdns.org"

        /** The default `User-Agent` header value. */
        public const val USER_AGENT: String = "oabp-kotlin-sdk/0.1.0"
    }
}

// --- internal A2A param wrappers (kept out of the public surface) ---

@kotlinx.serialization.Serializable
private data class MessageParams(
    val message: Message,
)

@kotlinx.serialization.Serializable
private data class IdParams(
    val id: String,
)

private fun requireId(
    value: String,
    field: String,
) {
    require(value.isNotBlank()) { "$field is required and must be non-blank" }
}

/**
 * Builds a JSON object param payload for ad-hoc A2A calls, e.g.
 * `client.a2a("tasks/get", jsonParams("id" to "t-1"))`.
 */
public fun jsonParams(vararg pairs: Pair<String, String>): JsonObject = JsonObject(pairs.associate { (k, v) -> k to JsonPrimitive(v) })
