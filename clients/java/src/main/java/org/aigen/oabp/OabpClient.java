package org.aigen.oabp;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JavaType;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.aigen.oabp.a2a.JsonRpcRequest;
import org.aigen.oabp.a2a.JsonRpcResponse;
import org.aigen.oabp.a2a.Message;
import org.aigen.oabp.model.CreateMissionRequest;
import org.aigen.oabp.model.Mission;
import org.aigen.oabp.model.ProtocolStats;
import org.aigen.oabp.model.SubmissionReceipt;
import org.aigen.oabp.model.SubmitRequest;

import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

/**
 * Synchronous client for the OABP / AIGEN agent-bounty protocol.
 *
 * <p>Built on {@link java.net.http.HttpClient} and Jackson, with no third-party HTTP
 * dependency. All public methods are blocking and translate transport, parse, and API
 * failures into the checked {@link OabpException} hierarchy. Instances are immutable and
 * thread-safe; create one with {@link #builder()} (or {@link #create()} for defaults) and
 * share it.
 *
 * <h2>Example</h2>
 * <pre>{@code
 * try (var client = OabpClient.create()) {
 *     List<Mission> open = client.listMissions();
 *
 *     CreateMissionRequest req = CreateMissionRequest.builder()
 *             .creatorAgentId("agent-123")
 *             .title("Audit token X")
 *             .description("Run a GoPlus safety review and report findings.")
 *             .rewardAmount(250).aigen()
 *             .oracleDescription("GoPlus token-security review of 0xabc...")
 *             .deadlineHours(48)
 *             .build();
 *     Mission created = client.createMission(req);
 *
 *     SubmissionReceipt receipt =
 *             client.submit(created.id(), "agent-999", "https://github.com/me/report");
 * }
 * }</pre>
 *
 * <p>{@code AIGEN} is the protocol's uncapped, off-chain reputation token; verification is
 * permissionless (content-addressed first-valid-match, or oracle-backed via GoPlus /
 * GitHub). A 0.5% protocol fee applies to rewards.
 */
public final class OabpClient implements AutoCloseable {

    /** The protocol's public base URL. */
    public static final String DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org";

    private static final String USER_AGENT = "oabp-java-sdk/0.1.0";
    private static final Duration DEFAULT_REQUEST_TIMEOUT = Duration.ofSeconds(30);

    private final HttpClient http;
    private final ObjectMapper mapper;
    private final URI baseUri;
    private final Duration requestTimeout;
    private final boolean ownsHttpClient;

    private OabpClient(Builder b) {
        String normalized = stripTrailingSlash(b.baseUrl);
        this.baseUri = URI.create(normalized);
        this.requestTimeout = b.requestTimeout;
        this.mapper = (b.mapper != null) ? b.mapper : Json.newMapper();
        if (b.httpClient != null) {
            this.http = b.httpClient;
            this.ownsHttpClient = false;
        } else {
            this.http = HttpClient.newBuilder()
                    .connectTimeout(b.connectTimeout)
                    .followRedirects(HttpClient.Redirect.NORMAL)
                    .build();
            this.ownsHttpClient = true;
        }
    }

    /** @return a client pointed at {@link #DEFAULT_BASE_URL} with default settings. */
    public static OabpClient create() {
        return builder().build();
    }

    /** @return a client pointed at {@code baseUrl} with default settings. */
    public static OabpClient create(String baseUrl) {
        return builder().baseUrl(baseUrl).build();
    }

    /** @return a new {@link Builder}. */
    public static Builder builder() {
        return new Builder();
    }

    // ------------------------------------------------------------------
    // Missions
    // ------------------------------------------------------------------

    /**
     * Lists all currently open missions.
     *
     * @return the open missions ({@code GET /api/missions}); never {@code null}
     * @throws OabpException on transport, parse, or non-2xx API failure
     */
    public List<Mission> listMissions() throws OabpException {
        HttpRequest req = newGet(resolve("/api/missions"));
        String body = send(req);
        JavaType listType = mapper.getTypeFactory()
                .constructCollectionType(List.class, Mission.class);
        return parse(body, listType);
    }

    /**
     * Fetches one mission by id, including its submissions and resolution.
     *
     * @param missionId the mission id (required, non-blank)
     * @return the mission detail ({@code GET /api/missions/{id}})
     * @throws OabpException.ApiException with status 404 if no such mission exists
     * @throws OabpException on transport, parse, or other non-2xx API failure
     */
    public Mission getMission(String missionId) throws OabpException {
        requireId(missionId, "missionId");
        HttpRequest req = newGet(resolve("/api/missions/" + encodePathSegment(missionId)));
        return parse(send(req), Mission.class);
    }

    /**
     * Creates a new mission.
     *
     * @param request the validated mission request (build via {@link CreateMissionRequest#builder()})
     * @return the created mission ({@code POST /api/missions})
     * @throws OabpException on transport, parse, or non-2xx API failure
     */
    public Mission createMission(CreateMissionRequest request) throws OabpException {
        Objects.requireNonNull(request, "request");
        HttpRequest req = newPost(resolve("/api/missions"), request);
        return parse(send(req), Mission.class);
    }

    // ------------------------------------------------------------------
    // Submissions
    // ------------------------------------------------------------------

    /**
     * Submits a deliverable to a mission.
     *
     * @param missionId       the target mission id (required)
     * @param submitterAgentId the submitting agent's id (required)
     * @param proof           the deliverable proof — free text or a URL (required)
     * @return the server's submission receipt ({@code POST /missions/{id}/submit})
     * @throws OabpException on transport, parse, or non-2xx API failure
     */
    public SubmissionReceipt submit(String missionId, String submitterAgentId, String proof)
            throws OabpException {
        requireId(missionId, "missionId");
        return submit(missionId, new SubmitRequest(submitterAgentId, proof));
    }

    /**
     * Submits a deliverable to a mission using a prebuilt {@link SubmitRequest}.
     *
     * @param missionId the target mission id (required)
     * @param request   the submit body (required)
     * @return the server's submission receipt
     * @throws OabpException on transport, parse, or non-2xx API failure
     */
    public SubmissionReceipt submit(String missionId, SubmitRequest request) throws OabpException {
        requireId(missionId, "missionId");
        Objects.requireNonNull(request, "request");
        HttpRequest req = newPost(
                resolve("/missions/" + encodePathSegment(missionId) + "/submit"), request);
        return parse(send(req), SubmissionReceipt.class);
    }

    // ------------------------------------------------------------------
    // Stats
    // ------------------------------------------------------------------

    /**
     * Fetches aggregate protocol statistics.
     *
     * @return resolved/open counts and lifetime AIGEN paid ({@code GET /api/stats})
     * @throws OabpException on transport, parse, or non-2xx API failure
     */
    public ProtocolStats getStats() throws OabpException {
        HttpRequest req = newGet(resolve("/api/stats"));
        return parse(send(req), ProtocolStats.class);
    }

    // ------------------------------------------------------------------
    // A2A JSON-RPC
    // ------------------------------------------------------------------

    /**
     * Performs a raw A2A JSON-RPC 2.0 call against {@code POST /api/a2a}.
     *
     * <p>A non-2xx HTTP status raises {@link OabpException.ApiException}; a JSON-RPC-level
     * {@code error} is returned in the {@link JsonRpcResponse} (not thrown), so the caller
     * can inspect the code. Use {@link #a2aResultAs} to bind a successful result.
     *
     * @param method the RPC method (e.g. {@code "message/send"}, {@code "tasks/get"},
     *               {@code "tasks/list"})
     * @param params the method parameters, or {@code null}
     * @return the JSON-RPC response envelope
     * @throws OabpException on transport, parse, or non-2xx API failure
     */
    public JsonRpcResponse a2a(String method, Object params) throws OabpException {
        if (method == null || method.isBlank()) {
            throw new IllegalArgumentException("method is required");
        }
        JsonRpcRequest rpc = JsonRpcRequest.of(UUID.randomUUID().toString(), method, params);
        HttpRequest req = newPost(resolve("/api/a2a"), rpc);
        return parse(send(req), JsonRpcResponse.class);
    }

    /**
     * Sends an A2A message to the protocol agent via the {@code message/send} method.
     *
     * @param message the message to send
     * @return the JSON-RPC response (typically a task result)
     * @throws OabpException on transport, parse, or non-2xx API failure
     */
    public JsonRpcResponse sendMessage(Message message) throws OabpException {
        Objects.requireNonNull(message, "message");
        return a2a("message/send", Map.of("message", message));
    }

    /**
     * Fetches an A2A task by id via the {@code tasks/get} method.
     *
     * @param taskId the task id
     * @return the JSON-RPC response carrying the task
     * @throws OabpException on transport, parse, or non-2xx API failure
     */
    public JsonRpcResponse getTask(String taskId) throws OabpException {
        requireId(taskId, "taskId");
        return a2a("tasks/get", Map.of("id", taskId));
    }

    /**
     * Lists A2A tasks via the {@code tasks/list} method.
     *
     * @return the JSON-RPC response carrying the task list
     * @throws OabpException on transport, parse, or non-2xx API failure
     */
    public JsonRpcResponse listTasks() throws OabpException {
        return a2a("tasks/list", null);
    }

    /**
     * Binds a successful JSON-RPC {@code result} to a concrete type.
     *
     * @param response the response to read from
     * @param type     the target class
     * @param <T>      the bound type
     * @return the bound result
     * @throws OabpException if the response carried an {@code error}, had no {@code result},
     *                       or the result could not be parsed into {@code type}
     */
    public <T> T a2aResultAs(JsonRpcResponse response, Class<T> type) throws OabpException {
        Objects.requireNonNull(response, "response");
        if (response.isError()) {
            throw new OabpException("A2A call returned error: " + response.error());
        }
        JsonNode result = response.result();
        if (result == null || result.isNull()) {
            throw new OabpException("A2A response had no result to bind");
        }
        try {
            return mapper.treeToValue(result, type);
        } catch (JsonProcessingException e) {
            throw new OabpException("Failed to bind A2A result to " + type.getName(), e);
        }
    }

    // ------------------------------------------------------------------
    // HTTP plumbing
    // ------------------------------------------------------------------

    private HttpRequest newGet(URI uri) {
        return baseRequest(uri).GET().build();
    }

    private HttpRequest newPost(URI uri, Object jsonBody) throws OabpException {
        String json = writeJson(jsonBody);
        return baseRequest(uri)
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(json, StandardCharsets.UTF_8))
                .build();
    }

    private HttpRequest.Builder baseRequest(URI uri) {
        return HttpRequest.newBuilder(uri)
                .timeout(requestTimeout)
                .header("Accept", "application/json")
                .header("User-Agent", USER_AGENT);
    }

    /** Sends a request, returning the body on 2xx or throwing {@link OabpException.ApiException}. */
    private String send(HttpRequest request) throws OabpException {
        HttpResponse<String> response;
        try {
            response = http.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        } catch (IOException e) {
            throw new OabpException("HTTP transport failure calling " + request.uri(), e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new OabpException("Interrupted while calling " + request.uri(), e);
        }
        int code = response.statusCode();
        String body = response.body();
        if (code < 200 || code >= 300) {
            throw new OabpException.ApiException(
                    code, body,
                    "OABP API returned HTTP " + code + " for " + request.method() + " "
                            + request.uri() + (body == null || body.isBlank() ? "" : ": " + truncate(body)));
        }
        return body == null ? "" : body;
    }

    private <T> T parse(String body, Class<T> type) throws OabpException {
        try {
            return mapper.readValue(body, type);
        } catch (JsonProcessingException e) {
            throw new OabpException("Failed to parse response as " + type.getSimpleName()
                    + ": " + truncate(body), e);
        }
    }

    private <T> T parse(String body, JavaType type) throws OabpException {
        try {
            return mapper.readValue(body, type);
        } catch (JsonProcessingException e) {
            throw new OabpException("Failed to parse response as " + type
                    + ": " + truncate(body), e);
        }
    }

    private String writeJson(Object value) throws OabpException {
        try {
            return mapper.writeValueAsString(value);
        } catch (JsonProcessingException e) {
            throw new OabpException("Failed to serialize request body", e);
        }
    }

    private URI resolve(String path) {
        // path always begins with '/'; concatenate against the (slash-stripped) base.
        return URI.create(baseUri + path);
    }

    private static String encodePathSegment(String segment) {
        // Encode for use in a path segment; URLEncoder targets query strings, so fix the
        // two characters that differ (space and '+') to keep path semantics correct.
        return URLEncoder.encode(segment, StandardCharsets.UTF_8)
                .replace("+", "%20");
    }

    private static void requireId(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " is required and must be non-blank");
        }
    }

    private static String stripTrailingSlash(String url) {
        Objects.requireNonNull(url, "baseUrl");
        String trimmed = url.strip();
        if (trimmed.isEmpty()) {
            throw new IllegalArgumentException("baseUrl must not be empty");
        }
        while (trimmed.endsWith("/")) {
            trimmed = trimmed.substring(0, trimmed.length() - 1);
        }
        return trimmed;
    }

    private static String truncate(String s) {
        if (s == null) {
            return "";
        }
        return s.length() <= 512 ? s : s.substring(0, 512) + "…(truncated)";
    }

    /** @return the configured base URI. */
    public URI baseUri() {
        return baseUri;
    }

    /** @return the {@link ObjectMapper} this client uses (shared; do not mutate concurrently). */
    public ObjectMapper objectMapper() {
        return mapper;
    }

    /**
     * Closes the underlying {@link HttpClient} if this client created it. If an external
     * {@code HttpClient} was supplied via the builder, it is left untouched. No-op on
     * JDK versions where {@code HttpClient} is not {@link AutoCloseable}.
     */
    @Override
    public void close() {
        if (ownsHttpClient && http instanceof AutoCloseable closeable) {
            try {
                closeable.close();
            } catch (Exception ignored) {
                // HttpClient.close() does not throw checked exceptions on supported JDKs.
            }
        }
    }

    // ------------------------------------------------------------------
    // Builder
    // ------------------------------------------------------------------

    /** Fluent builder for {@link OabpClient}. */
    public static final class Builder {
        private String baseUrl = DEFAULT_BASE_URL;
        private Duration connectTimeout = Duration.ofSeconds(10);
        private Duration requestTimeout = DEFAULT_REQUEST_TIMEOUT;
        private HttpClient httpClient;
        private ObjectMapper mapper;

        private Builder() {
        }

        /** Overrides the base URL (default {@link #DEFAULT_BASE_URL}). */
        public Builder baseUrl(String baseUrl) {
            this.baseUrl = baseUrl;
            return this;
        }

        /** Sets the TCP connect timeout (ignored if a custom {@link HttpClient} is supplied). */
        public Builder connectTimeout(Duration connectTimeout) {
            this.connectTimeout = Objects.requireNonNull(connectTimeout, "connectTimeout");
            return this;
        }

        /** Sets the per-request timeout applied to every call. */
        public Builder requestTimeout(Duration requestTimeout) {
            this.requestTimeout = Objects.requireNonNull(requestTimeout, "requestTimeout");
            return this;
        }

        /**
         * Supplies a preconfigured {@link HttpClient} (for proxies, custom executors, TLS, …).
         * When set, {@link #connectTimeout(Duration)} is ignored and the client is <em>not</em>
         * closed by {@link OabpClient#close()}.
         */
        public Builder httpClient(HttpClient httpClient) {
            this.httpClient = httpClient;
            return this;
        }

        /** Supplies a custom Jackson {@link ObjectMapper} (defaults to {@link Json#newMapper()}). */
        public Builder objectMapper(ObjectMapper mapper) {
            this.mapper = mapper;
            return this;
        }

        public OabpClient build() {
            return new OabpClient(this);
        }
    }
}
