package org.aigen.oabp.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.Optional;

/**
 * The server's acknowledgement of a {@code POST /missions/{id}/submit} call.
 *
 * <p>The exact JSON shape returned by the protocol on submit is intentionally loosely
 * bound: the server may return the created {@link Submission}, an {@code accepted} flag
 * computed synchronously (for first-valid-match missions), and/or a status string. All
 * fields are optional and unknown JSON is ignored.
 *
 * @param submissionId server-assigned id of the new submission, if returned
 * @param missionId    the mission the submission was filed against, if echoed back
 * @param accepted     synchronous validity verdict, if the server decided immediately
 * @param status       free-text status (e.g. {@code "pending"}, {@code "accepted"}), if any
 * @param message      human-readable detail, if any
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record SubmissionReceipt(
        @JsonProperty("submission_id") String submissionId,
        @JsonProperty("mission_id") String missionId,
        @JsonProperty("accepted") Boolean accepted,
        @JsonProperty("status") String status,
        @JsonProperty("message") String message) {

    /** @return whether the server reported the submission as accepted (false if undecided). */
    public boolean isAccepted() {
        return Boolean.TRUE.equals(accepted);
    }

    /** @return the status string, if present. */
    public Optional<String> statusOpt() {
        return Optional.ofNullable(status);
    }

    /** @return the message string, if present. */
    public Optional<String> messageOpt() {
        return Optional.ofNullable(message);
    }
}
