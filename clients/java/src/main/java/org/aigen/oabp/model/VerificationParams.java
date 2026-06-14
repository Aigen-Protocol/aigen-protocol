package org.aigen.oabp.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.Optional;

/**
 * Parameters that configure how a mission is verified, paired with its
 * {@link VerificationType}.
 *
 * <ul>
 *   <li>For {@link VerificationType#FIRST_VALID_MATCH}, {@code regex} holds the pattern a
 *       submitted proof must match for the (first) submitter to win.</li>
 *   <li>For {@link VerificationType#ORACLE}, {@code oracleDescription} describes what the
 *       oracle checks (e.g. a token-security review or a GitHub repo deliverable).</li>
 * </ul>
 *
 * <p>Both fields are optional; accessors return {@link Optional} so callers never trip on
 * {@code null}. Unknown JSON properties are ignored for forward compatibility.
 *
 * @param regex             regex for content-addressed matching, may be {@code null}
 * @param oracleDescription human-readable description of the oracle check, may be {@code null}
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
@JsonIgnoreProperties(ignoreUnknown = true)
public record VerificationParams(
        @JsonProperty("regex") String regex,
        @JsonProperty("oracle_description") String oracleDescription) {

    /** @return an empty params object (no regex, no oracle description). */
    public static VerificationParams empty() {
        return new VerificationParams(null, null);
    }

    /** @return params carrying only a {@code regex}, for first-valid-match missions. */
    public static VerificationParams ofRegex(String regex) {
        return new VerificationParams(regex, null);
    }

    /** @return params carrying only an {@code oracle_description}, for oracle missions. */
    public static VerificationParams ofOracle(String oracleDescription) {
        return new VerificationParams(null, oracleDescription);
    }

    /** @return the matching regex, if present. */
    public Optional<String> regexOpt() {
        return Optional.ofNullable(regex);
    }

    /** @return the oracle description, if present. */
    public Optional<String> oracleDescriptionOpt() {
        return Optional.ofNullable(oracleDescription);
    }
}
