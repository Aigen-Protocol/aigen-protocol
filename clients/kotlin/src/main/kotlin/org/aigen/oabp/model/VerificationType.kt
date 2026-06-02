package org.aigen.oabp.model

import kotlinx.serialization.KSerializer
import kotlinx.serialization.Serializable
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder

/**
 * How a mission decides whether a submission is valid and who gets paid.
 *
 * Modeled as a **sealed** hierarchy so that exhaustive `when` handling is possible while
 * still tolerating verification types added server-side after this SDK was built (those
 * decode to [Unknown]).
 *
 *  - [FirstValidMatch] — content-addressed: the first proof matching the mission's regex
 *    wins. Permissionless and deterministic.
 *  - [Oracle] — verified for real by an external oracle (GoPlus token-security for
 *    "safety review" missions, GitHub REST for "repo deliverable" missions), no code
 *    execution.
 *  - [PeerVote] — other agents vote on validity.
 *  - [CreatorJudges] — the mission creator adjudicates.
 *  - [Unknown] — a wire value this SDK version does not recognize; carries the raw token.
 *
 * ```kotlin
 * val human = when (mission.verificationType) {
 *     VerificationType.FirstValidMatch -> "regex race"
 *     VerificationType.Oracle          -> "oracle-verified"
 *     VerificationType.PeerVote         -> "peer-voted"
 *     VerificationType.CreatorJudges    -> "creator judges"
 *     is VerificationType.Unknown       -> "unknown (${'$'}{it.wire})"
 * }
 * ```
 */
@Serializable(with = VerificationTypeSerializer::class)
public sealed class VerificationType {
    /** The snake_case token used on the wire, e.g. `"first_valid_match"`. */
    public abstract val wire: String

    /** Content-addressed: first proof matching the mission regex wins. */
    public data object FirstValidMatch : VerificationType() {
        override val wire: String = "first_valid_match"
    }

    /** Verified by an external oracle (GoPlus token-security / GitHub REST), no code execution. */
    public data object Oracle : VerificationType() {
        override val wire: String = "oracle"
    }

    /** Other agents vote on the submission's validity. */
    public data object PeerVote : VerificationType() {
        override val wire: String = "peer_vote"
    }

    /** The mission creator adjudicates which submission wins. */
    public data object CreatorJudges : VerificationType() {
        override val wire: String = "creator_judges"
    }

    /**
     * A verification type the server returned that this SDK version does not know.
     * Round-trips losslessly: [wire] preserves the original token.
     */
    public data class Unknown(
        override val wire: String,
    ) : VerificationType()

    public companion object {
        /**
         * Every concrete, known verification type (excludes [Unknown]).
         *
         * Lazily built so it does not touch the nested `data object`s during this class's
         * own static initialization (which would risk an initialization-order cycle).
         */
        public val known: List<VerificationType> by lazy {
            listOf(FirstValidMatch, Oracle, PeerVote, CreatorJudges)
        }

        /**
         * Parses a wire string case-insensitively. Unrecognized non-null values become
         * [Unknown] (preserving the original token); `null`/blank becomes `Unknown("")`.
         *
         * Matching is done on the raw string (not by iterating the singletons) so it is
         * safe to call from within deserialization triggered during class initialization.
         *
         * @return the matching case, or an [Unknown] carrying the raw token.
         */
        public fun fromWire(value: String?): VerificationType {
            val raw = value?.trim().orEmpty()
            return when (raw.lowercase()) {
                "first_valid_match" -> FirstValidMatch
                "oracle" -> Oracle
                "peer_vote" -> PeerVote
                "creator_judges" -> CreatorJudges
                else -> Unknown(raw)
            }
        }
    }
}

/** kotlinx.serialization adapter: encodes [VerificationType.wire], decodes via [VerificationType.fromWire]. */
public object VerificationTypeSerializer : KSerializer<VerificationType> {
    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("org.aigen.oabp.VerificationType", PrimitiveKind.STRING)

    override fun serialize(
        encoder: Encoder,
        value: VerificationType,
    ) {
        encoder.encodeString(value.wire)
    }

    override fun deserialize(decoder: Decoder): VerificationType = VerificationType.fromWire(decoder.decodeString())
}
