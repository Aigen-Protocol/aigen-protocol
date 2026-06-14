package org.aigen.oabp.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * The server's acknowledgement of a `POST /missions/{id}/submit` call.
 *
 * The exact JSON shape returned on submit is intentionally loosely bound: the server may
 * return the created submission id, an `accepted` flag computed synchronously (for
 * first-valid-match missions), and/or a status string. All fields are optional and unknown
 * JSON is ignored.
 *
 * @property submissionId server-assigned id of the new submission, if returned.
 * @property missionId the mission the submission was filed against, if echoed back.
 * @property accepted synchronous validity verdict, if the server decided immediately.
 * @property status free-text status (e.g. `"pending"`, `"accepted"`), if any.
 * @property message human-readable detail, if any.
 */
@Serializable
public data class SubmissionReceipt(
    @SerialName("submission_id")
    val submissionId: String? = null,
    @SerialName("mission_id")
    val missionId: String? = null,
    val accepted: Boolean? = null,
    val status: String? = null,
    val message: String? = null,
) {
    /** Whether the server reported the submission as accepted (`false` if undecided). */
    public val isAccepted: Boolean
        get() = accepted == true
}
