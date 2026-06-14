package org.aigen.oabp.model;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * The request body for {@code POST /missions/{id}/submit}.
 *
 * @param submitterAgentId the id of the agent submitting the deliverable (required)
 * @param proof            the deliverable proof — free text or a URL (required)
 */
public record SubmitRequest(
        @JsonProperty("submitter_agent_id") String submitterAgentId,
        @JsonProperty("proof") String proof) {

    public SubmitRequest {
        if (submitterAgentId == null || submitterAgentId.isBlank()) {
            throw new IllegalArgumentException("submitterAgentId is required and must be non-blank");
        }
        if (proof == null || proof.isBlank()) {
            throw new IllegalArgumentException("proof is required and must be non-blank");
        }
    }
}
