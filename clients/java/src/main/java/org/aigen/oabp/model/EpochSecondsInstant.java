package org.aigen.oabp.model;

import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.core.JsonToken;
import com.fasterxml.jackson.databind.DeserializationContext;
import com.fasterxml.jackson.databind.JsonDeserializer;
import com.fasterxml.jackson.databind.JsonSerializer;
import com.fasterxml.jackson.databind.SerializerProvider;

import java.io.IOException;
import java.math.BigDecimal;
import java.time.Instant;

/**
 * Jackson (de)serializers that map the protocol's <em>unix-seconds</em> timestamps
 * (e.g. {@code deadline}, {@code submitted_at}) to/from {@link Instant}.
 *
 * <p>The OABP API expresses times as integer seconds since the epoch, optionally with a
 * fractional part. Jackson's stock {@code InstantDeserializer} (under jsr310) can be
 * configured for this, but the threshold between "seconds" and "milliseconds" is easy to
 * get wrong; these helpers make the seconds contract explicit and also accept a numeric
 * string (some gateways stringify numbers). On serialization we always emit whole seconds
 * as a JSON number, matching what the server expects in request bodies.
 *
 * <p>This class is not instantiable; use the nested {@link Deser} / {@link Ser}.
 */
public final class EpochSecondsInstant {

    private EpochSecondsInstant() {
    }

    /** Deserializes a numeric (or numeric-string) unix-seconds value into an {@link Instant}. */
    public static final class Deser extends JsonDeserializer<Instant> {
        @Override
        public Instant deserialize(JsonParser p, DeserializationContext ctxt) throws IOException {
            JsonToken t = p.currentToken();
            if (t == JsonToken.VALUE_NULL) {
                return null;
            }
            final BigDecimal seconds;
            if (t == JsonToken.VALUE_NUMBER_INT || t == JsonToken.VALUE_NUMBER_FLOAT) {
                seconds = p.getDecimalValue();
            } else if (t == JsonToken.VALUE_STRING) {
                String raw = p.getText().trim();
                if (raw.isEmpty()) {
                    return null;
                }
                try {
                    seconds = new BigDecimal(raw);
                } catch (NumberFormatException nfe) {
                    throw new IOException("Expected unix-seconds timestamp, got: \"" + raw + "\"", nfe);
                }
            } else {
                throw new IOException("Expected numeric unix-seconds timestamp, got token " + t);
            }
            long epochSecond = seconds.longValue();
            // Preserve any fractional second as nanos.
            BigDecimal fraction = seconds.subtract(BigDecimal.valueOf(epochSecond));
            long nanos = fraction.movePointRight(9).longValue();
            return Instant.ofEpochSecond(epochSecond, nanos);
        }
    }

    /** Serializes an {@link Instant} as integer unix-seconds (truncating sub-second precision). */
    public static final class Ser extends JsonSerializer<Instant> {
        @Override
        public void serialize(Instant value, JsonGenerator gen, SerializerProvider provider) throws IOException {
            gen.writeNumber(value.getEpochSecond());
        }
    }
}
