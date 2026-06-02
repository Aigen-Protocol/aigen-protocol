package org.aigen.oabp.model

import kotlinx.serialization.KSerializer
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder
import kotlinx.serialization.json.JsonDecoder
import kotlinx.serialization.json.JsonEncoder
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.JsonUnquotedLiteral
import java.math.BigDecimal

/**
 * Serializes [BigDecimal] as a JSON **number** (not a string) so token / stablecoin
 * amounts round-trip exactly.
 *
 * Reward amounts and lifetime totals are monetary quantities: using `Double` would lose
 * precision for large or fractional values. On decode this accepts a JSON number or a
 * numeric string; on encode it emits the canonical decimal form as an unquoted literal.
 */
public object BigDecimalSerializer : KSerializer<BigDecimal> {
    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("org.aigen.oabp.BigDecimal", PrimitiveKind.DOUBLE)

    override fun serialize(
        encoder: Encoder,
        value: BigDecimal,
    ) {
        // Emit a bare JSON number with full precision when we have a JSON encoder;
        // otherwise fall back to a double for generic formats.
        if (encoder is JsonEncoder) {
            encoder.encodeJsonElement(JsonUnquotedLiteral(value.toPlainString()))
        } else {
            encoder.encodeDouble(value.toDouble())
        }
    }

    override fun deserialize(decoder: Decoder): BigDecimal {
        if (decoder is JsonDecoder) {
            val element = decoder.decodeJsonElement()
            val primitive =
                element as? JsonPrimitive
                    ?: throw IllegalArgumentException("Expected a numeric amount, got: $element")
            val raw = primitive.content.trim()
            require(raw.isNotEmpty()) { "Empty numeric amount" }
            return runCatching { BigDecimal(raw) }.getOrElse {
                throw IllegalArgumentException("Expected a numeric amount, got: \"$raw\"", it)
            }
        }
        return BigDecimal.valueOf(decoder.decodeDouble())
    }
}
