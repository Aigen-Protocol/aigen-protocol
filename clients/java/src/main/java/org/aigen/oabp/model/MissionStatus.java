package org.aigen.oabp.model;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

/**
 * Lifecycle state of a mission as reported by the server.
 *
 * <p>The protocol mints {@code open} missions, may move them to {@code in_review}
 * while a submission is being verified, and settles them as {@code resolved}
 * (paid out) or {@code expired} (deadline passed with no valid submission).
 * Unknown server states map to {@link #UNKNOWN}.
 */
public enum MissionStatus {
    OPEN("open"),
    IN_REVIEW("in_review"),
    RESOLVED("resolved"),
    EXPIRED("expired"),
    CANCELLED("cancelled"),
    /** Sentinel for a status unknown to this SDK version. */
    UNKNOWN(null);

    private final String wire;

    MissionStatus(String wire) {
        this.wire = wire;
    }

    /**
     * @return the wire token, e.g. {@code "open"}.
     * @throws IllegalStateException if called on {@link #UNKNOWN}.
     */
    @JsonValue
    public String wireValue() {
        if (wire == null) {
            throw new IllegalStateException("MissionStatus.UNKNOWN has no wire representation");
        }
        return wire;
    }

    /** @return {@code true} if the mission is settled (resolved, expired, or cancelled). */
    public boolean isTerminal() {
        return this == RESOLVED || this == EXPIRED || this == CANCELLED;
    }

    /**
     * Parses a wire string, case-insensitively, never throwing on unknown input.
     *
     * @param value raw status string, may be {@code null}
     * @return the matching constant, or {@link #UNKNOWN}
     */
    @JsonCreator
    public static MissionStatus fromWire(String value) {
        if (value == null) {
            return UNKNOWN;
        }
        for (MissionStatus s : values()) {
            if (s.wire != null && s.wire.equalsIgnoreCase(value)) {
                return s;
            }
        }
        return UNKNOWN;
    }
}
