package org.aigen.oabp.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Parameters that configure how a mission is verified, paired with its [VerificationType].
 *
 *  - For [VerificationType.FirstValidMatch], [regex] holds the pattern a submitted proof
 *    must match for the (first) submitter to win.
 *  - For [VerificationType.Oracle], [oracleDescription] describes what the oracle checks
 *    (e.g. a token-security review or a GitHub repo deliverable).
 *
 * Both fields are optional; unknown JSON properties are ignored by the SDK's `Json`
 * configuration for forward compatibility. Null fields are omitted when serialized.
 *
 * @property regex regex for content-addressed matching, or `null`.
 * @property oracleDescription human-readable description of the oracle check, or `null`.
 */
@Serializable
public data class VerificationParams(
    val regex: String? = null,
    @SerialName("oracle_description")
    val oracleDescription: String? = null,
) {
    public companion object {
        /** Empty params object (no regex, no oracle description). */
        public val EMPTY: VerificationParams = VerificationParams()

        /** Params carrying only a [regex], for first-valid-match missions. */
        public fun ofRegex(regex: String): VerificationParams = VerificationParams(regex = regex)

        /** Params carrying only an [oracleDescription], for oracle missions. */
        public fun ofOracle(oracleDescription: String): VerificationParams = VerificationParams(oracleDescription = oracleDescription)
    }
}
