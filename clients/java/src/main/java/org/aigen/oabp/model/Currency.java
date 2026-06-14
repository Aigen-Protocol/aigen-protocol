package org.aigen.oabp.model;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

/**
 * The settlement unit of a mission reward.
 *
 * <ul>
 *   <li>{@link #AIGEN} — the protocol's uncapped, off-chain reputation/points token.</li>
 *   <li>{@link #USDC} — a real-value stablecoin payout.</li>
 * </ul>
 *
 * <p>Deserialization is tolerant of unknown/extra currencies the server may add later:
 * any unrecognized value maps to {@link #UNKNOWN} rather than throwing, so a new
 * server-side currency never breaks an older client. {@link #UNKNOWN} is never sent
 * back to the server (it has no wire value of its own — see {@link #wireValue()}).
 */
public enum Currency {
    AIGEN("AIGEN"),
    USDC("USDC"),
    /** Sentinel for a currency the server returned that this SDK version does not know. */
    UNKNOWN(null);

    private final String wire;

    Currency(String wire) {
        this.wire = wire;
    }

    /**
     * @return the exact token used on the wire, e.g. {@code "AIGEN"}.
     * @throws IllegalStateException if called on {@link #UNKNOWN}, which has no wire form.
     */
    @JsonValue
    public String wireValue() {
        if (wire == null) {
            throw new IllegalStateException("Currency.UNKNOWN has no wire representation");
        }
        return wire;
    }

    /**
     * Parses a wire string, case-insensitively, never throwing on unknown input.
     *
     * @param value raw currency string from JSON, may be {@code null}
     * @return the matching constant, or {@link #UNKNOWN} if unrecognized/null
     */
    @JsonCreator
    public static Currency fromWire(String value) {
        if (value == null) {
            return UNKNOWN;
        }
        for (Currency c : values()) {
            if (c.wire != null && c.wire.equalsIgnoreCase(value)) {
                return c;
            }
        }
        return UNKNOWN;
    }
}
