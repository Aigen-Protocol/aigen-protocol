package org.aigen.oabp.a2a;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;

import java.util.Optional;

/**
 * A JSON-RPC 2.0 response envelope from the A2A endpoint.
 *
 * <p>Exactly one of {@code result} / {@code error} is populated per the spec. The
 * {@code result} is kept as a raw {@link JsonNode} so callers can bind it to whatever
 * concrete type the invoked method returns (e.g. a task object); {@link #resultAs} is a
 * convenience that does this binding given an {@link com.fasterxml.jackson.databind.ObjectMapper}.
 *
 * @param jsonrpc protocol tag, always {@code "2.0"}
 * @param id      correlation id matching the request
 * @param result  the method result, present on success
 * @param error   the error object, present on failure
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record JsonRpcResponse(
        @JsonProperty("jsonrpc") String jsonrpc,
        @JsonProperty("id") String id,
        @JsonProperty("result") JsonNode result,
        @JsonProperty("error") JsonRpcError error) {

    /** @return {@code true} if this response carries an {@code error}. */
    public boolean isError() {
        return error != null;
    }

    /** @return the error object, if present. */
    public Optional<JsonRpcError> errorOpt() {
        return Optional.ofNullable(error);
    }

    /** @return the raw result node, if present. */
    public Optional<JsonNode> resultOpt() {
        return Optional.ofNullable(result);
    }
}
