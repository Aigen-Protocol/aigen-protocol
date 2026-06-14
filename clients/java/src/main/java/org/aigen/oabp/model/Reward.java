package org.aigen.oabp.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.math.BigDecimal;

/**
 * The bounty attached to a mission: an {@code amount} in a given {@link Currency}.
 *
 * <p>The amount is modeled as {@link BigDecimal} (not {@code double}) so that token
 * and stablecoin quantities round-trip exactly. {@code AIGEN} is the protocol's
 * uncapped, off-chain points token; {@code USDC} is real value.
 *
 * @param amount   the gross reward quantity (before the protocol fee), never {@code null}
 * @param currency the settlement unit
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record Reward(
        @JsonProperty("amount") BigDecimal amount,
        @JsonProperty("currency") Currency currency) {

    /** The protocol fee, expressed as a fraction (0.5%). */
    public static final BigDecimal PROTOCOL_FEE_RATE = new BigDecimal("0.005");

    public Reward {
        if (amount == null) {
            amount = BigDecimal.ZERO;
        }
        if (currency == null) {
            currency = Currency.UNKNOWN;
        }
    }

    /**
     * The amount the winner actually receives after the 0.5% protocol fee is deducted.
     *
     * @return {@code amount * (1 - 0.005)}, with the same currency
     */
    public BigDecimal netAmount() {
        return amount.multiply(BigDecimal.ONE.subtract(PROTOCOL_FEE_RATE));
    }

    /**
     * The 0.5% protocol fee taken from this reward.
     *
     * @return {@code amount * 0.005}
     */
    public BigDecimal protocolFee() {
        return amount.multiply(PROTOCOL_FEE_RATE);
    }
}
