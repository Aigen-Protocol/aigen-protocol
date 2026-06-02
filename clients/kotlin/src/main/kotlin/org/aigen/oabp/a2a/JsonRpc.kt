package org.aigen.oabp.a2a

import kotlinx.serialization.EncodeDefault
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

/**
 * A JSON-RPC 2.0 request envelope for the A2A endpoint (`POST /api/a2a`).
 *
 * Used for the agent-to-agent methods `message/send`, `tasks/get` and `tasks/list`. The
 * [params] payload is a raw [JsonElement] so any method's parameter shape can be carried
 * without a bespoke type per method.
 *
 * @property jsonrpc protocol tag, always `"2.0"`.
 * @property id correlation id echoed back in the response.
 * @property method the RPC method name.
 * @property params method parameters (or `null` for no-arg methods).
 */
@Serializable
public data class JsonRpcRequest(
    // Always emitted: JSON-RPC 2.0 requires the "jsonrpc" tag on the wire even though the
    // SDK's Json omits other defaults (encodeDefaults = false).
    @EncodeDefault(EncodeDefault.Mode.ALWAYS)
    val jsonrpc: String = "2.0",
    val id: String,
    val method: String,
    val params: JsonElement? = null,
)

/**
 * A JSON-RPC 2.0 response envelope from the A2A endpoint.
 *
 * Exactly one of [result] / [error] is populated per the spec. The [result] is kept as a
 * raw [JsonElement] so callers can decode it to whatever concrete type the invoked method
 * returns (e.g. a task object).
 *
 * @property jsonrpc protocol tag, always `"2.0"`.
 * @property id correlation id matching the request.
 * @property result the method result, present on success.
 * @property error the error object, present on failure.
 */
@Serializable
public data class JsonRpcResponse(
    val jsonrpc: String = "2.0",
    val id: String? = null,
    val result: JsonElement? = null,
    val error: JsonRpcError? = null,
) {
    /** `true` if this response carries an [error]. */
    public val isError: Boolean
        get() = error != null
}

/**
 * A JSON-RPC 2.0 error object, as carried in the `error` member of a response.
 *
 * @property code numeric error code (JSON-RPC reserved range, or A2A-specific).
 * @property message short human-readable description.
 * @property data optional structured detail (kept as a raw [JsonElement]).
 */
@Serializable
public data class JsonRpcError(
    val code: Int,
    val message: String? = null,
    val data: JsonElement? = null,
)

/**
 * An A2A message: a [role] plus an ordered list of [parts].
 *
 * This is the payload sent under `message/send`. The text-part shape is modeled directly
 * (the common case for agent prompts); other part kinds still round-trip because [Part]
 * keeps unknown JSON via the SDK's lenient `Json` configuration.
 *
 * @property role `"user"` or `"agent"`.
 * @property parts the message content parts.
 */
@Serializable
public data class Message(
    val role: String,
    val parts: List<Part> = emptyList(),
) {
    /**
     * A single content part of a [Message]. A text part has `kind = "text"` and a [text]
     * value; unknown kinds are tolerated.
     *
     * @property kind the part kind, e.g. `"text"`.
     * @property text the text content for text parts, otherwise `null`.
     */
    @Serializable
    public data class Part(
        val kind: String,
        val text: String? = null,
    ) {
        public companion object {
            /** A text part wrapping [text]. */
            public fun text(text: String): Part = Part(kind = "text", text = text)
        }
    }

    public companion object {
        /** A `user` message carrying a single text part. */
        public fun userText(text: String): Message = Message(role = "user", parts = listOf(Part.text(text)))
    }
}

/**
 * The well-known A2A agent card (subset) served at `/.well-known/agent-card.json`.
 *
 * Only the commonly used fields are modeled; the SDK's lenient `Json` keeps unknown
 * properties so a richer card still parses.
 *
 * @property name human-readable agent name.
 * @property description what the agent does.
 * @property url the A2A JSON-RPC endpoint URL advertised by the card.
 * @property version the agent/card version string.
 */
@Serializable
public data class AgentCard(
    val name: String? = null,
    val description: String? = null,
    val url: String? = null,
    val version: String? = null,
    @SerialName("preferredTransport")
    val preferredTransport: String? = null,
)
