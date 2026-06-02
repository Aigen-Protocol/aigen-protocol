package org.aigen.oabp.a2a;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;

/**
 * A JSON-RPC 2.0 error object, as carried in the {@code error} member of a response.
 *
 * @param code    numeric error code (JSON-RPC reserved range, or A2A-specific)
 * @param message short human-readable description
 * @param data    optional structured detail (kept as a raw {@link JsonNode})
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record JsonRpcError(
        @JsonProperty("code") int code,
        @JsonProperty("message") String message,
        @JsonProperty("data") JsonNode data) {

    @Override
    public String toString() {
        return "JsonRpcError{code=" + code + ", message='" + message + "'"
                + (data != null ? ", data=" + data : "") + "}";
    }
}
