package org.aigen.oabp.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;
import com.fasterxml.jackson.databind.annotation.JsonSerialize;

import java.time.Instant;
import java.util.Optional;

/**
 * A deliverable submitted against a mission by an agent.
 *
 * <p>{@code proof} is the agent's submitted artifact — free text or a URL. For
 * first-valid-match missions it is matched against the mission regex; for oracle
 * missions it is the input the oracle verifies (e.g. a token address or a GitHub
 * repository URL).
 *
 * @param id              server-assigned submission id, may be {@code null} on freshly built objects
 * @param submitterAgentId the agent that submitted, may be {@code null}
 * @param proof           the submitted proof (text or URL)
 * @param accepted        whether this submission was accepted as valid, may be {@code null} if undecided
 * @param submittedAt     submission time (unix seconds on the wire), may be {@code null}
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record Submission(
        @JsonProperty("id") String id,
        @JsonProperty("submitter_agent_id") String submitterAgentId,
        @JsonProperty("proof") String proof,
        @JsonProperty("accepted") Boolean accepted,
        @JsonProperty("submitted_at")
        @JsonSerialize(using = EpochSecondsInstant.Ser.class)
        @JsonDeserialize(using = EpochSecondsInstant.Deser.class)
        Instant submittedAt) {

    /** @return whether this submission was explicitly accepted (false if undecided/rejected). */
    public boolean isAccepted() {
        return Boolean.TRUE.equals(accepted);
    }

    /** @return the submission time, if known. */
    public Optional<Instant> submittedAtOpt() {
        return Optional.ofNullable(submittedAt);
    }
}
