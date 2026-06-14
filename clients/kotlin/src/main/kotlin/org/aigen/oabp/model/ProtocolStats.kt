package org.aigen.oabp.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import java.math.BigDecimal

/**
 * Aggregate protocol counters from `GET /api/stats`.
 *
 * @property resolved number of missions that have settled.
 * @property open number of missions currently open.
 * @property lifetimeRewardAigenPaid total AIGEN paid out over the protocol's lifetime.
 */
@Serializable
public data class ProtocolStats(
    val resolved: Long = 0,
    val open: Long = 0,
    @SerialName("lifetime_reward_aigen_paid")
    @Serializable(with = BigDecimalSerializer::class)
    val lifetimeRewardAigenPaid: BigDecimal = BigDecimal.ZERO,
) {
    /** Total missions seen (open + resolved). */
    public val total: Long
        get() = resolved + open
}
