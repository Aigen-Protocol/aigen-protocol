package org.aigen.oabp.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * The request body for `POST /missions/{id}/submit`.
 *
 * @property submitterAgentId the id of the agent submitting the deliverable (required, non-blank).
 * @property proof the deliverable proof — free text or a URL (required, non-blank).
 */
@Serializable
public data class SubmitRequest(
    @SerialName("submitter_agent_id")
    val submitterAgentId: String,
    val proof: String,
) {
    init {
        require(submitterAgentId.isNotBlank()) { "submitterAgentId is required and must be non-blank" }
        require(proof.isNotBlank()) { "proof is required and must be non-blank" }
    }
}
