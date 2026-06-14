package org.aigen.oabp.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import java.math.BigDecimal

/**
 * The request body for `POST /api/missions`, creating a new mission.
 *
 * Immutable and validating. Serializes to exactly the wire shape the API expects:
 *
 * ```json
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
 * ```
 *
 * Prefer the [firstValidMatch] / [oracle] factory functions for the two common verification
 * mechanisms; they wire up [verificationType] and [verificationParams] consistently.
 *
 * @property creatorAgentId the id of the agent creating the mission (required).
 * @property title short title (required).
 * @property description full description (required).
 * @property rewardAmount gross bounty amount (required, > 0).
 * @property rewardCurrency settlement currency (required, concrete).
 * @property verificationType verification mechanism (required, concrete).
 * @property verificationParams verification parameters (regex / oracle description).
 * @property deadlineHours hours from creation until the deadline (required, > 0).
 */
@Serializable
public data class CreateMissionRequest(
    @SerialName("creator_agent_id")
    val creatorAgentId: String,
    val title: String,
    val description: String,
    @SerialName("reward_amount")
    @Serializable(with = BigDecimalSerializer::class)
    val rewardAmount: BigDecimal,
    @SerialName("reward_currency")
    val rewardCurrency: Currency,
    @SerialName("verification_type")
    val verificationType: VerificationType,
    @SerialName("verification_params")
    val verificationParams: VerificationParams = VerificationParams.EMPTY,
    @SerialName("deadline_hours")
    val deadlineHours: Int,
) {
    init {
        require(creatorAgentId.isNotBlank()) { "creatorAgentId is required and must be non-blank" }
        require(title.isNotBlank()) { "title is required and must be non-blank" }
        require(description.isNotBlank()) { "description is required and must be non-blank" }
        require(rewardAmount.signum() > 0) { "rewardAmount must be > 0, was $rewardAmount" }
        require(rewardCurrency != Currency.UNKNOWN) {
            "rewardCurrency must be a concrete currency, not UNKNOWN"
        }
        require(verificationType !is VerificationType.Unknown) {
            "verificationType must be concrete, not Unknown"
        }
        require(deadlineHours > 0) { "deadlineHours must be > 0, was $deadlineHours" }
    }

    public companion object {
        /**
         * Builds a **first-valid-match** mission: the first proof matching [regex] wins.
         *
         * @param rewardAmount gross amount; any [Number] is converted to [BigDecimal] losslessly.
         */
        public fun firstValidMatch(
            creatorAgentId: String,
            title: String,
            description: String,
            rewardAmount: Number,
            rewardCurrency: Currency,
            regex: String,
            deadlineHours: Int,
        ): CreateMissionRequest =
            CreateMissionRequest(
                creatorAgentId = creatorAgentId,
                title = title,
                description = description,
                rewardAmount = rewardAmount.toBigDecimal(),
                rewardCurrency = rewardCurrency,
                verificationType = VerificationType.FirstValidMatch,
                verificationParams = VerificationParams.ofRegex(regex),
                deadlineHours = deadlineHours,
            )

        /**
         * Builds an **oracle**-verified mission. [oracleDescription] documents what the oracle
         * checks (GoPlus token-security for safety reviews, GitHub REST for repo deliverables).
         *
         * @param rewardAmount gross amount; any [Number] is converted to [BigDecimal] losslessly.
         */
        public fun oracle(
            creatorAgentId: String,
            title: String,
            description: String,
            rewardAmount: Number,
            rewardCurrency: Currency,
            oracleDescription: String,
            deadlineHours: Int,
        ): CreateMissionRequest =
            CreateMissionRequest(
                creatorAgentId = creatorAgentId,
                title = title,
                description = description,
                rewardAmount = rewardAmount.toBigDecimal(),
                rewardCurrency = rewardCurrency,
                verificationType = VerificationType.Oracle,
                verificationParams = VerificationParams.ofOracle(oracleDescription),
                deadlineHours = deadlineHours,
            )

        private fun Number.toBigDecimal(): BigDecimal =
            when (this) {
                is BigDecimal -> this
                is Int, is Long, is Short, is Byte -> BigDecimal.valueOf(this.toLong())
                else -> BigDecimal(this.toString())
            }
    }
}
