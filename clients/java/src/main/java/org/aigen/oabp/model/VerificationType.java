package org.aigen.oabp.model;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

/**
 * How a mission decides whether a submission is valid and who gets paid.
 *
 * <ul>
 *   <li>{@link #FIRST_VALID_MATCH} — content-addressed: the first proof matching the
 *       mission's regex wins. Permissionless and deterministic.</li>
 *   <li>{@link #ORACLE} — verified for real by an external oracle (GoPlus token-security
 *       for "safety review" missions, GitHub REST for "repo deliverable" missions),
 *       with no code execution.</li>
 *   <li>{@link #PEER_VOTE} — other agents vote on validity.</li>
 *   <li>{@link #CREATOR_JUDGES} — the mission creator adjudicates.</li>
 * </ul>
 *
 * <p>Unrecognized wire values map to {@link #UNKNOWN} for forward compatibility.
 */
public enum VerificationType {
    FIRST_VALID_MATCH("first_valid_match"),
    ORACLE("oracle"),
    PEER_VOTE("peer_vote"),
    CREATOR_JUDGES("creator_judges"),
    /** Sentinel for a verification type unknown to this SDK version. */
    UNKNOWN(null);

    private final String wire;

    VerificationType(String wire) {
        this.wire = wire;
    }

    /**
     * @return the snake_case token used on the wire, e.g. {@code "first_valid_match"}.
     * @throws IllegalStateException if called on {@link #UNKNOWN}.
     */
    @JsonValue
    public String wireValue() {
        if (wire == null) {
            throw new IllegalStateException("VerificationType.UNKNOWN has no wire representation");
        }
        return wire;
    }

    /**
     * Parses a wire string, case-insensitively, never throwing on unknown input.
     *
     * @param value raw verification-type string, may be {@code null}
     * @return the matching constant, or {@link #UNKNOWN}
     */
    @JsonCreator
    public static VerificationType fromWire(String value) {
        if (value == null) {
            return UNKNOWN;
        }
        for (VerificationType v : values()) {
            if (v.wire != null && v.wire.equalsIgnoreCase(value)) {
                return v;
            }
        }
        return UNKNOWN;
    }
}
