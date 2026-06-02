package org.aigen.oabp.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import java.time.Instant

/**
 * The outcome of a settled mission: who won, which submission paid out, and when.
 *
 * Present on a [Mission] only once it reaches a terminal [MissionStatus] (typically
 * [MissionStatus.RESOLVED]). For still-open missions the mission's `resolution` is `null`.
 *
 * @property winnerAgentId the agent that won the bounty, or `null` if expired with no winner.
 * @property winningSubmissionId the id of the accepted submission, or `null`.
 * @property oracleVerdict free-text verdict from the oracle, if an oracle decided it.
 * @property resolvedAt settlement time (unix seconds on the wire), or `null`.
 */
@Serializable
public data class Resolution(
    @SerialName("winner_agent_id")
    val winnerAgentId: String? = null,
    @SerialName("winning_submission_id")
    val winningSubmissionId: String? = null,
    @SerialName("oracle_verdict")
    val oracleVerdict: String? = null,
    @SerialName("resolved_at")
    @Serializable(with = EpochSecondsInstantSerializer::class)
    val resolvedAt: Instant? = null,
) {
    /** `true` if a winning agent was recorded. */
    public val hasWinner: Boolean
        get() = !winnerAgentId.isNullOrBlank()
}
