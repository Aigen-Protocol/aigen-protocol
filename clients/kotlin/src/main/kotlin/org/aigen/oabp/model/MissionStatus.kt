package org.aigen.oabp.model

import kotlinx.serialization.KSerializer
import kotlinx.serialization.Serializable
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder

/**
 * Lifecycle state of a mission as reported by the server.
 *
 * The protocol mints `open` missions, may move them to `in_review` while a submission is
 * being verified, and settles them as `resolved` (paid out) or `expired` (deadline passed
 * with no valid submission). Unknown server states map to [UNKNOWN].
 */
@Serializable(with = MissionStatusSerializer::class)
public enum class MissionStatus(
    public val wire: String?,
) {
    OPEN("open"),
    IN_REVIEW("in_review"),
    RESOLVED("resolved"),
    EXPIRED("expired"),
    CANCELLED("cancelled"),

    /** Sentinel for a status unknown to this SDK version. */
    UNKNOWN(null),
    ;

    /**
     * The wire token, e.g. `"open"`.
     *
     * @throws IllegalStateException if called on [UNKNOWN].
     */
    public fun wireValue(): String = wire ?: error("MissionStatus.UNKNOWN has no wire representation")

    /** `true` if the mission is settled (resolved, expired, or cancelled). */
    public val isTerminal: Boolean
        get() = this == RESOLVED || this == EXPIRED || this == CANCELLED

    public companion object {
        /**
         * Parses a wire string case-insensitively, never throwing on unknown input.
         *
         * @return the matching constant, or [UNKNOWN].
         */
        public fun fromWire(value: String?): MissionStatus {
            if (value == null) return UNKNOWN
            return entries.firstOrNull { it.wire != null && it.wire.equals(value, ignoreCase = true) }
                ?: UNKNOWN
        }
    }
}

/** kotlinx.serialization adapter: encodes [MissionStatus.wireValue], decodes via [MissionStatus.fromWire]. */
public object MissionStatusSerializer : KSerializer<MissionStatus> {
    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("org.aigen.oabp.MissionStatus", PrimitiveKind.STRING)

    override fun serialize(
        encoder: Encoder,
        value: MissionStatus,
    ) {
        encoder.encodeString(value.wireValue())
    }

    override fun deserialize(decoder: Decoder): MissionStatus = MissionStatus.fromWire(decoder.decodeString())
}
