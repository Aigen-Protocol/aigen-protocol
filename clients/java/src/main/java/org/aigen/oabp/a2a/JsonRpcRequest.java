package org.aigen.oabp.a2a;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * A JSON-RPC 2.0 request envelope for the A2A endpoint ({@code POST /api/a2a}).
 *
 * <p>Used for the agent-to-agent methods {@code message/send}, {@code tasks/get} and
 * {@code tasks/list}. The {@code params} payload is left as an arbitrary object so any
 * method's parameter shape can be carried without a bespoke type per method.
 *
 * @param jsonrpc protocol tag, always {@code "2.0"}
 * @param id      correlation id echoed back in the response
 * @param method  the RPC method name
 * @param params  method parameters (may be {@code null} for no-arg methods)
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record JsonRpcRequest(
        @JsonProperty("jsonrpc") String jsonrpc,
        @JsonProperty("id") String id,
        @JsonProperty("method") String method,
        @JsonProperty("params") Object params) {

    /** Builds a well-formed 2.0 request with the given id, method and params. */
    public static JsonRpcRequest of(String id, String method, Object params) {
        return new JsonRpcRequest("2.0", id, method, params);
    }
}
