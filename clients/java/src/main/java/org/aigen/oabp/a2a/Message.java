package org.aigen.oabp.a2a;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/**
 * An A2A message: a {@code role} plus an ordered list of {@code parts}.
 *
 * <p>This is the payload sent under {@code message/send}. Only the text-part shape is
 * modeled directly (the common case for agent prompts); arbitrary part kinds still
 * round-trip because {@link Part} keeps unknown JSON.
 *
 * @param role  {@code "user"} or {@code "agent"}
 * @param parts the message content parts (never {@code null})
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
@JsonIgnoreProperties(ignoreUnknown = true)
public record Message(
        @JsonProperty("role") String role,
        @JsonProperty("parts") List<Part> parts) {

    public Message {
        parts = (parts == null) ? List.of() : List.copyOf(parts);
    }

    /** @return a {@code user} message carrying a single text part. */
    public static Message userText(String text) {
        return new Message("user", List.of(Part.text(text)));
    }

    /**
     * A single content part of a {@link Message}. A text part has {@code kind="text"} and a
     * {@code text} value; unknown kinds are tolerated.
     *
     * @param kind the part kind, e.g. {@code "text"}
     * @param text the text content for text parts, otherwise {@code null}
     */
    @JsonInclude(JsonInclude.Include.NON_NULL)
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Part(
            @JsonProperty("kind") String kind,
            @JsonProperty("text") String text) {

        /** @return a text part wrapping {@code text}. */
        public static Part text(String text) {
            return new Part("text", text);
        }
    }
}
