package org.aigen.oabp;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;

/**
 * Factory for the {@link ObjectMapper} the SDK uses to (de)serialize OABP payloads.
 *
 * <p>Centralizes Jackson configuration so the wire contract is consistent everywhere:
 * unknown properties are ignored (forward compatibility), {@code java.time} types are
 * supported, timestamps are never written as numeric arrays, and {@code null} fields are
 * omitted from request bodies. The mapper is thread-safe once built.
 */
public final class Json {

    private Json() {
    }

    /** @return a freshly configured, independent {@link ObjectMapper}. */
    public static ObjectMapper newMapper() {
        return new ObjectMapper()
                .registerModule(new JavaTimeModule())
                .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false)
                .configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, false)
                .configure(SerializationFeature.FAIL_ON_EMPTY_BEANS, false);
    }
}
