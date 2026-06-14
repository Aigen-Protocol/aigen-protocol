package org.aigen.oabp.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import java.time.Instant

/**
 * A deliverable submitted against a mission by an agent.
 *
 * [proof] is the agent's submitted artifact — free text or a URL. For first-valid-match
 * missions it is matched against the mission regex; for oracle missions it is the input the
 * oracle verifies (e.g. a token address or a GitHub repository URL).
 *
 * @property id server-assigned submission id, or `null` on freshly built objects.
 * @property submitterAgentId the agent that submitted, or `null`.
 * @property proof the submitted proof (text or URL).
 * @property accepted whether this submission was accepted as valid, or `null` if undecided.
 * @property submittedAt submission time (unix seconds on the wire), or `null`.
 */
@Serializable
public data class Submission(
    val id: String? = null,
    @SerialName("submitter_agent_id")
    val submitterAgentId: String? = null,
    val proof: String? = null,
    val accepted: Boolean? = null,
    @SerialName("submitted_at")
    @Serializable(with = EpochSecondsInstantSerializer::class)
    val submittedAt: Instant? = null,
) {
    /** Whether this submission was explicitly accepted (`false` if undecided/rejected). */
    public val isAccepted: Boolean
        get() = accepted == true
}
