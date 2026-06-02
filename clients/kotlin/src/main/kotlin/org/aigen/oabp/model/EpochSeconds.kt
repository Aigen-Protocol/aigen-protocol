package org.aigen.oabp.model

import kotlinx.serialization.KSerializer
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder
import kotlinx.serialization.json.JsonDecoder
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonPrimitive
import java.math.BigDecimal
import java.time.Instant

/**
 * kotlinx.serialization [KSerializer] mapping the protocol's **unix-seconds** timestamps
 * (`deadline`, `submitted_at`, `resolved_at`, …) to/from [java.time.Instant].
 *
 * The OABP API expresses times as a number of seconds since the epoch, optionally with a
 * fractional part. This serializer:
 *
 *  - accepts a JSON number (int or float) **or** a numeric string (some gateways stringify
 *    numbers), preserving any fractional second as nanoseconds;
 *  - emits whole seconds as a JSON number on the way out, matching what the server expects
 *    in request bodies.
 *
 * Apply it with `@Serializable(with = EpochSecondsInstantSerializer::class)` on the field,
 * or `@Contextual` together with [EpochSecondsInstantSerializer] registered in the module.
 */
public object EpochSecondsInstantSerializer : KSerializer<Instant> {
    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("org.aigen.oabp.EpochSecondsInstant", PrimitiveKind.LONG)

    override fun serialize(
        encoder: Encoder,
        value: Instant,
    ) {
        // Always emit whole unix-seconds as a JSON number.
        encoder.encodeLong(value.epochSecond)
    }

    override fun deserialize(decoder: Decoder): Instant {
        val seconds: BigDecimal =
            if (decoder is JsonDecoder) {
                // Robust path: tolerate numeric strings as well as bare numbers.
                val element = decoder.decodeJsonElement()
                val primitive =
                    element as? JsonPrimitive
                        ?: throw IllegalArgumentException(
                            "Expected a unix-seconds timestamp, got: $element",
                        )
                val raw = primitive.content.trim()
                require(raw.isNotEmpty()) { "Empty unix-seconds timestamp" }
                runCatching { BigDecimal(raw) }.getOrElse {
                    throw IllegalArgumentException("Expected a unix-seconds timestamp, got: \"$raw\"", it)
                }
            } else {
                // Generic decoders (rare for this SDK): read a double.
                BigDecimal.valueOf(decoder.decodeDouble())
            }
        return seconds.toInstant()
    }

    private fun BigDecimal.toInstant(): Instant {
        val epochSecond = this.toLong()
        val fraction = this.subtract(BigDecimal.valueOf(epochSecond))
        val nanos = fraction.movePointRight(9).toLong()
        return Instant.ofEpochSecond(epochSecond, nanos)
    }
}

/**
 * Convenience wrapper used by [org.aigen.oabp.model.EpochSecondsInstantSerializer] callers that
 * decode a timestamp out of a raw [JsonPrimitive] (e.g. inside custom A2A handling).
 */
internal fun JsonPrimitive.toEpochSecondsInstant(): Instant {
    val raw = this.jsonPrimitive.content.trim()
    return EpochSecondsInstantSerializer.run {
        val bd = BigDecimal(raw)
        val epochSecond = bd.toLong()
        val nanos = bd.subtract(BigDecimal.valueOf(epochSecond)).movePointRight(9).toLong()
        Instant.ofEpochSecond(epochSecond, nanos)
    }
}
