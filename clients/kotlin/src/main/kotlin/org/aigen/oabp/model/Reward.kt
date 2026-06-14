package org.aigen.oabp.model

import kotlinx.serialization.Serializable
import java.math.BigDecimal

/**
 * The bounty attached to a mission: an [amount] in a given [Currency].
 *
 * The amount is a [BigDecimal] (not `Double`) so token and stablecoin quantities round-trip
 * exactly. `AIGEN` is the protocol's uncapped, off-chain points token; `USDC` is real value.
 *
 * @property amount the gross reward quantity (before the 0.5% protocol fee).
 * @property currency the settlement unit.
 */
@Serializable
public data class Reward(
    @Serializable(with = BigDecimalSerializer::class)
    val amount: BigDecimal,
    val currency: Currency,
) {
    /** The amount the winner actually receives after the 0.5% protocol fee: `amount * (1 - 0.005)`. */
    public val netAmount: BigDecimal
        get() = amount.multiply(BigDecimal.ONE.subtract(PROTOCOL_FEE_RATE))

    /** The 0.5% protocol fee taken from this reward: `amount * 0.005`. */
    public val protocolFee: BigDecimal
        get() = amount.multiply(PROTOCOL_FEE_RATE)

    public companion object {
        /** The protocol fee, expressed as a fraction (0.5%). */
        public val PROTOCOL_FEE_RATE: BigDecimal = BigDecimal("0.005")
    }
}
