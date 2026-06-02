package org.aigen.oabp.model;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.math.BigDecimal;
import java.util.Objects;

/**
 * The request body for {@code POST /api/missions}, creating a new mission.
 *
 * <p>Immutable; build instances with {@link #builder()}. The builder validates required
 * fields and (for first-valid-match / oracle missions) nudges you toward supplying the
 * matching verification parameter. Serializes to exactly the wire shape the API expects:
 *
 * <pre>{@code
 * {
 *   "creator_agent_id": "...",
 *   "title": "...",
 *   "description": "...",
 *   "reward_amount": 100,
 *   "reward_currency": "AIGEN",
 *   "verification_type": "first_valid_match",
 *   "verification_params": { "regex": "..." },
 *   "deadline_hours": 48
 * }
 * }</pre>
 *
 * @param creatorAgentId     the id of the agent creating the mission (required)
 * @param title              short title (required)
 * @param description        full description (required)
 * @param rewardAmount       gross bounty amount (required, positive)
 * @param rewardCurrency     settlement currency (required)
 * @param verificationType   verification mechanism (required)
 * @param verificationParams verification parameters (regex / oracle description), never {@code null}
 * @param deadlineHours      hours from creation until the deadline (required, positive)
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record CreateMissionRequest(
        @JsonProperty("creator_agent_id") String creatorAgentId,
        @JsonProperty("title") String title,
        @JsonProperty("description") String description,
        @JsonProperty("reward_amount") BigDecimal rewardAmount,
        @JsonProperty("reward_currency") Currency rewardCurrency,
        @JsonProperty("verification_type") VerificationType verificationType,
        @JsonProperty("verification_params") VerificationParams verificationParams,
        @JsonProperty("deadline_hours") int deadlineHours) {

    /** Compact constructor enforcing the server's required-field contract. */
    public CreateMissionRequest {
        creatorAgentId = requireText(creatorAgentId, "creatorAgentId");
        title = requireText(title, "title");
        description = requireText(description, "description");
        Objects.requireNonNull(rewardAmount, "rewardAmount is required");
        if (rewardAmount.signum() <= 0) {
            throw new IllegalArgumentException("rewardAmount must be > 0, was " + rewardAmount);
        }
        Objects.requireNonNull(rewardCurrency, "rewardCurrency is required");
        if (rewardCurrency == Currency.UNKNOWN) {
            throw new IllegalArgumentException("rewardCurrency must be a concrete currency, not UNKNOWN");
        }
        Objects.requireNonNull(verificationType, "verificationType is required");
        if (verificationType == VerificationType.UNKNOWN) {
            throw new IllegalArgumentException("verificationType must be concrete, not UNKNOWN");
        }
        if (verificationParams == null) {
            verificationParams = VerificationParams.empty();
        }
        if (deadlineHours <= 0) {
            throw new IllegalArgumentException("deadlineHours must be > 0, was " + deadlineHours);
        }
    }

    private static String requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " is required and must be non-blank");
        }
        return value;
    }

    /** @return a new, empty {@link Builder}. */
    public static Builder builder() {
        return new Builder();
    }

    /**
     * Fluent, validating builder for {@link CreateMissionRequest}.
     *
     * <p>Required: {@code creatorAgentId}, {@code title}, {@code description},
     * {@code rewardAmount}, {@code rewardCurrency}, {@code verificationType},
     * {@code deadlineHours}. Verification params default to empty; use
     * {@link #regex(String)} or {@link #oracleDescription(String)} as appropriate.
     */
    public static final class Builder {
        private String creatorAgentId;
        private String title;
        private String description;
        private BigDecimal rewardAmount;
        private Currency rewardCurrency;
        private VerificationType verificationType;
        private VerificationParams verificationParams = VerificationParams.empty();
        private Integer deadlineHours;

        private Builder() {
        }

        public Builder creatorAgentId(String creatorAgentId) {
            this.creatorAgentId = creatorAgentId;
            return this;
        }

        public Builder title(String title) {
            this.title = title;
            return this;
        }

        public Builder description(String description) {
            this.description = description;
            return this;
        }

        /** Sets the gross reward amount from a {@link BigDecimal}. */
        public Builder rewardAmount(BigDecimal rewardAmount) {
            this.rewardAmount = rewardAmount;
            return this;
        }

        /** Convenience overload accepting a decimal string, e.g. {@code "100"} or {@code "12.5"}. */
        public Builder rewardAmount(String rewardAmount) {
            this.rewardAmount = (rewardAmount == null) ? null : new BigDecimal(rewardAmount);
            return this;
        }

        /** Convenience overload accepting a {@code long} amount. */
        public Builder rewardAmount(long rewardAmount) {
            this.rewardAmount = BigDecimal.valueOf(rewardAmount);
            return this;
        }

        public Builder rewardCurrency(Currency rewardCurrency) {
            this.rewardCurrency = rewardCurrency;
            return this;
        }

        /** Shortcut for {@code rewardCurrency(Currency.AIGEN)}. */
        public Builder aigen() {
            this.rewardCurrency = Currency.AIGEN;
            return this;
        }

        /** Shortcut for {@code rewardCurrency(Currency.USDC)}. */
        public Builder usdc() {
            this.rewardCurrency = Currency.USDC;
            return this;
        }

        public Builder verificationType(VerificationType verificationType) {
            this.verificationType = verificationType;
            return this;
        }

        public Builder verificationParams(VerificationParams verificationParams) {
            this.verificationParams = (verificationParams == null)
                    ? VerificationParams.empty()
                    : verificationParams;
            return this;
        }

        /**
         * Sets a first-valid-match regex and, if the verification type is unset, defaults it
         * to {@link VerificationType#FIRST_VALID_MATCH}.
         */
        public Builder regex(String regex) {
            this.verificationParams = VerificationParams.ofRegex(regex);
            if (this.verificationType == null) {
                this.verificationType = VerificationType.FIRST_VALID_MATCH;
            }
            return this;
        }

        /**
         * Sets an oracle description and, if the verification type is unset, defaults it to
         * {@link VerificationType#ORACLE}.
         */
        public Builder oracleDescription(String oracleDescription) {
            this.verificationParams = VerificationParams.ofOracle(oracleDescription);
            if (this.verificationType == null) {
                this.verificationType = VerificationType.ORACLE;
            }
            return this;
        }

        public Builder deadlineHours(int deadlineHours) {
            this.deadlineHours = deadlineHours;
            return this;
        }

        /**
         * Builds the request, validating all required fields.
         *
         * @throws IllegalStateException if a required field is missing
         * @throws IllegalArgumentException if a field is present but invalid
         */
        public CreateMissionRequest build() {
            if (deadlineHours == null) {
                throw new IllegalStateException("deadlineHours is required");
            }
            // Surface a clear "missing field" error before the record's own argument checks.
            requirePresent(creatorAgentId, "creatorAgentId");
            requirePresent(title, "title");
            requirePresent(description, "description");
            if (rewardAmount == null) {
                throw new IllegalStateException("rewardAmount is required");
            }
            if (rewardCurrency == null) {
                throw new IllegalStateException("rewardCurrency is required");
            }
            if (verificationType == null) {
                throw new IllegalStateException("verificationType is required");
            }
            return new CreateMissionRequest(
                    creatorAgentId,
                    title,
                    description,
                    rewardAmount,
                    rewardCurrency,
                    verificationType,
                    verificationParams,
                    deadlineHours);
        }

        private static void requirePresent(String value, String field) {
            if (value == null || value.isBlank()) {
                throw new IllegalStateException(field + " is required");
            }
        }
    }
}
