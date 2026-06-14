package org.aigen.oabp.model

import kotlinx.serialization.KSerializer
import kotlinx.serialization.Serializable
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder

/**
 * The settlement unit of a mission reward.
 *
 *  - [AIGEN] — the protocol's uncapped, off-chain reputation/points token.
 *  - [USDC] — a real-value stablecoin payout.
 *
 * Deserialization is tolerant of currencies the server may add later: any unrecognized
 * value maps to [UNKNOWN] rather than throwing, so a new server-side currency never breaks
 * an older client. [UNKNOWN] has no wire form and must never be sent back to the server
 * (see [wireValue]).
 */
@Serializable(with = CurrencySerializer::class)
public enum class Currency(
    public val wire: String?,
) {
    AIGEN("AIGEN"),
    USDC("USDC"),

    /** Sentinel for a currency the server returned that this SDK version does not know. */
    UNKNOWN(null),
    ;

    /**
     * The exact token used on the wire, e.g. `"AIGEN"`.
     *
     * @throws IllegalStateException if called on [UNKNOWN], which has no wire form.
     */
    public fun wireValue(): String = wire ?: error("Currency.UNKNOWN has no wire representation")

    public companion object {
        /**
         * Parses a wire string case-insensitively, never throwing on unknown input.
         *
         * @return the matching constant, or [UNKNOWN] if unrecognized/null.
         */
        public fun fromWire(value: String?): Currency {
            if (value == null) return UNKNOWN
            return entries.firstOrNull { it.wire != null && it.wire.equals(value, ignoreCase = true) }
                ?: UNKNOWN
        }
    }
}

/** kotlinx.serialization adapter: encodes [Currency.wireValue], decodes via [Currency.fromWire]. */
public object CurrencySerializer : KSerializer<Currency> {
    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("org.aigen.oabp.Currency", PrimitiveKind.STRING)

    override fun serialize(
        encoder: Encoder,
        value: Currency,
    ) {
        encoder.encodeString(value.wireValue())
    }

    override fun deserialize(decoder: Decoder): Currency = Currency.fromWire(decoder.decodeString())
}
