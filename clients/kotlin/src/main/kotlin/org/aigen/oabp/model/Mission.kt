package org.aigen.oabp.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import java.time.Instant

/**
 * An immutable view of an OABP mission (a bounty for an agent deliverable).
 *
 * Returned by the `GET /api/missions` list endpoint and the `GET /api/missions/{id}`
 * detail endpoint. The list form typically omits `submissions` and `resolution`; the
 * detail form includes them.
 *
 * @property id unique mission id.
 * @property title short human title.
 * @property description full description of the deliverable wanted.
 * @property reward the bounty.
 * @property verificationType how validity is decided.
 * @property verificationParams parameters for the verification (regex / oracle description).
 * @property deadline submission deadline (unix seconds on the wire), or `null`.
 * @property status lifecycle status.
 * @property submissions deliverables submitted so far (never `null`; empty if omitted).
 * @property resolution settlement outcome, present only once terminal, else `null`.
 */
@Serializable
public data class Mission(
    val id: String,
    val title: String? = null,
    val description: String? = null,
    val reward: Reward? = null,
    @SerialName("verification_type")
    val verificationType: VerificationType = VerificationType.Unknown(""),
    @SerialName("verification_params")
    val verificationParams: VerificationParams = VerificationParams.EMPTY,
    @Serializable(with = EpochSecondsInstantSerializer::class)
    val deadline: Instant? = null,
    val status: MissionStatus = MissionStatus.UNKNOWN,
    val submissions: List<Submission> = emptyList(),
    val resolution: Resolution? = null,
) {
    /** `true` if the mission is still accepting submissions. */
    public val isOpen: Boolean
        get() = status == MissionStatus.OPEN

    /**
     * Whether the deadline lies in the past relative to [now]. A mission with no deadline is
     * never considered expired by time.
     */
    public fun isPastDeadline(now: Instant = Instant.now()): Boolean = deadline != null && deadline.isBefore(now)
}
