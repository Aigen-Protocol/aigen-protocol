package org.aigen.oabp.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;
import com.fasterxml.jackson.databind.annotation.JsonSerialize;

import java.time.Instant;
import java.util.Optional;

/**
 * The outcome of a settled mission: who won, which submission paid out, and when.
 *
 * <p>Present on a {@link Mission} only once it reaches a terminal {@link MissionStatus}
 * (typically {@link MissionStatus#RESOLVED}). For still-open missions the mission's
 * {@code resolution} is {@code null} and {@link Mission#resolutionOpt()} is empty.
 *
 * @param winnerAgentId      the agent that won the bounty, may be {@code null} if expired with no winner
 * @param winningSubmissionId the id of the accepted submission, may be {@code null}
 * @param oracleVerdict      free-text verdict from the oracle, if an oracle decided it
 * @param resolvedAt         settlement time (unix seconds on the wire), may be {@code null}
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record Resolution(
        @JsonProperty("winner_agent_id") String winnerAgentId,
        @JsonProperty("winning_submission_id") String winningSubmissionId,
        @JsonProperty("oracle_verdict") String oracleVerdict,
        @JsonProperty("resolved_at")
        @JsonSerialize(using = EpochSecondsInstant.Ser.class)
        @JsonDeserialize(using = EpochSecondsInstant.Deser.class)
        Instant resolvedAt) {

    /** @return {@code true} if a winning agent was recorded. */
    public boolean hasWinner() {
        return winnerAgentId != null && !winnerAgentId.isBlank();
    }

    /** @return the oracle's verdict text, if any. */
    public Optional<String> oracleVerdictOpt() {
        return Optional.ofNullable(oracleVerdict);
    }

    /** @return the settlement time, if known. */
    public Optional<Instant> resolvedAtOpt() {
        return Optional.ofNullable(resolvedAt);
    }
}
