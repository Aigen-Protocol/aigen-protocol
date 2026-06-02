package org.aigen.oabp.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;
import com.fasterxml.jackson.databind.annotation.JsonSerialize;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

/**
 * An immutable view of an OABP mission (a bounty for an agent deliverable).
 *
 * <p>Returned by the {@code GET /api/missions} list endpoint and the
 * {@code GET /api/missions/{id}} detail endpoint. The list form typically omits
 * {@code submissions} and {@code resolution}; the detail form includes them. All
 * collection fields are defensively copied and exposed as unmodifiable lists, so a
 * {@code Mission} is safe to share across threads.
 *
 * @param id                 unique mission id
 * @param title              short human title
 * @param description        full description of the deliverable wanted
 * @param reward             the bounty ({@link Reward})
 * @param verificationType   how validity is decided ({@link VerificationType})
 * @param verificationParams parameters for the verification (regex / oracle description)
 * @param deadline           submission deadline (unix seconds on the wire)
 * @param status             lifecycle {@link MissionStatus}
 * @param submissions        deliverables submitted so far (never {@code null} after construction)
 * @param resolution         settlement outcome, present only once terminal; may be {@code null}
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record Mission(
        @JsonProperty("id") String id,
        @JsonProperty("title") String title,
        @JsonProperty("description") String description,
        @JsonProperty("reward") Reward reward,
        @JsonProperty("verification_type") VerificationType verificationType,
        @JsonProperty("verification_params") VerificationParams verificationParams,
        @JsonProperty("deadline")
        @JsonSerialize(using = EpochSecondsInstant.Ser.class)
        @JsonDeserialize(using = EpochSecondsInstant.Deser.class)
        Instant deadline,
        @JsonProperty("status") MissionStatus status,
        @JsonProperty("submissions") List<Submission> submissions,
        @JsonProperty("resolution") Resolution resolution) {

    /** Canonical constructor: normalizes nulls and makes {@code submissions} unmodifiable. */
    public Mission {
        if (verificationType == null) {
            verificationType = VerificationType.UNKNOWN;
        }
        if (verificationParams == null) {
            verificationParams = VerificationParams.empty();
        }
        if (status == null) {
            status = MissionStatus.UNKNOWN;
        }
        submissions = (submissions == null)
                ? List.of()
                : List.copyOf(submissions);
    }

    /** @return the submission deadline, if the server provided one. */
    public Optional<Instant> deadlineOpt() {
        return Optional.ofNullable(deadline);
    }

    /** @return the settlement outcome, present only once the mission is terminal. */
    public Optional<Resolution> resolutionOpt() {
        return Optional.ofNullable(resolution);
    }

    /** @return {@code true} if the mission is still accepting submissions. */
    public boolean isOpen() {
        return status == MissionStatus.OPEN;
    }

    /**
     * Whether the deadline lies in the past relative to {@code now}. A mission with no
     * deadline is never considered expired by time.
     *
     * @param now reference instant
     * @return {@code true} if a deadline exists and is before {@code now}
     */
    public boolean isPastDeadline(Instant now) {
        return deadline != null && deadline.isBefore(now);
    }
}
