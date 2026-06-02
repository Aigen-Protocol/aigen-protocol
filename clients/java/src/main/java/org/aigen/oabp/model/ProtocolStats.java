package org.aigen.oabp.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.math.BigDecimal;

/**
 * Aggregate protocol counters from {@code GET /api/stats}.
 *
 * @param resolved               number of missions that have settled
 * @param open                   number of missions currently open
 * @param lifetimeRewardAigenPaid total AIGEN paid out over the protocol's lifetime
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record ProtocolStats(
        @JsonProperty("resolved") long resolved,
        @JsonProperty("open") long open,
        @JsonProperty("lifetime_reward_aigen_paid") BigDecimal lifetimeRewardAigenPaid) {

    public ProtocolStats {
        if (lifetimeRewardAigenPaid == null) {
            lifetimeRewardAigenPaid = BigDecimal.ZERO;
        }
    }

    /** @return total missions seen (open + resolved). */
    public long total() {
        return resolved + open;
    }
}
