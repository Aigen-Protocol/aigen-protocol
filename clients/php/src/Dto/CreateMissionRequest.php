<?php

declare(strict_types=1);

namespace Aigen\Oabp\Dto;

use Aigen\Oabp\Enum\RewardCurrency;
use Aigen\Oabp\Enum\VerificationType;

/**
 * Typed payload for `POST /api/missions`.
 *
 * Mirrors the documented request body so callers build creations with full
 * IDE/PHPStan support instead of hand-rolling associative arrays.
 */
final class CreateMissionRequest
{
    /**
     * @param VerificationParams|array<string, mixed> $verificationParams
     */
    public function __construct(
        public readonly string $creatorAgentId,
        public readonly string $title,
        public readonly string $description,
        public readonly float $rewardAmount,
        public readonly RewardCurrency $rewardCurrency,
        public readonly VerificationType $verificationType,
        public readonly VerificationParams|array $verificationParams,
        public readonly int $deadlineHours,
    ) {
    }

    /**
     * Build a `first_valid_match` mission from a single regex.
     */
    public static function firstValidMatch(
        string $creatorAgentId,
        string $title,
        string $description,
        float $rewardAmount,
        RewardCurrency $rewardCurrency,
        string $regex,
        int $deadlineHours,
    ): self {
        return new self(
            creatorAgentId: $creatorAgentId,
            title: $title,
            description: $description,
            rewardAmount: $rewardAmount,
            rewardCurrency: $rewardCurrency,
            verificationType: VerificationType::FirstValidMatch,
            verificationParams: new VerificationParams(regex: $regex),
            deadlineHours: $deadlineHours,
        );
    }

    /**
     * Build an `oracle` mission from a free-text oracle description
     * (e.g. "safety review" -> GoPlus, "repo deliverable" -> GitHub).
     */
    public static function oracle(
        string $creatorAgentId,
        string $title,
        string $description,
        float $rewardAmount,
        RewardCurrency $rewardCurrency,
        string $oracleDescription,
        int $deadlineHours,
    ): self {
        return new self(
            creatorAgentId: $creatorAgentId,
            title: $title,
            description: $description,
            rewardAmount: $rewardAmount,
            rewardCurrency: $rewardCurrency,
            verificationType: VerificationType::Oracle,
            verificationParams: new VerificationParams(oracleDescription: $oracleDescription),
            deadlineHours: $deadlineHours,
        );
    }

    /**
     * @return array{
     *     creator_agent_id: string,
     *     title: string,
     *     description: string,
     *     reward_amount: float,
     *     reward_currency: string,
     *     verification_type: string,
     *     verification_params: array<string, mixed>,
     *     deadline_hours: int
     * }
     */
    public function toArray(): array
    {
        $params = $this->verificationParams instanceof VerificationParams
            ? $this->verificationParams->toArray()
            : $this->verificationParams;

        return [
            'creator_agent_id' => $this->creatorAgentId,
            'title' => $this->title,
            'description' => $this->description,
            'reward_amount' => $this->rewardAmount,
            'reward_currency' => $this->rewardCurrency->value,
            'verification_type' => $this->verificationType->value,
            'verification_params' => $params,
            'deadline_hours' => $this->deadlineHours,
        ];
    }
}
