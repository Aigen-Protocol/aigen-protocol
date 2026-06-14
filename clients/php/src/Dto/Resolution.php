<?php

declare(strict_types=1);

namespace Aigen\Oabp\Dto;

/**
 * The outcome of a resolved mission.
 *
 * Shape varies by verification type, so only commonly-present fields are typed
 * and the full payload is preserved in {@see Resolution::$raw}.
 *
 * @phpstan-type ResolutionShape array{
 *     winner_agent_id?: string|null,
 *     winning_submission_id?: int|string|null,
 *     reward_paid?: int|float|string|null,
 *     oracle_result?: mixed,
 *     resolved_at?: int|string|null,
 *     ...
 * }
 */
final class Resolution
{
    /**
     * @param mixed                $oracleResult Raw oracle output, when present.
     * @param array<string, mixed> $raw          The untouched API payload.
     */
    public function __construct(
        public readonly ?string $winnerAgentId,
        public readonly ?string $winningSubmissionId,
        public readonly ?float $rewardPaid,
        public readonly mixed $oracleResult,
        public readonly ?int $resolvedAt,
        public readonly array $raw = [],
    ) {
    }

    /**
     * @param ResolutionShape $data
     */
    public static function fromArray(array $data): self
    {
        return new self(
            winnerAgentId: isset($data['winner_agent_id'])
                ? (string) $data['winner_agent_id']
                : null,
            winningSubmissionId: isset($data['winning_submission_id'])
                ? (string) $data['winning_submission_id']
                : null,
            rewardPaid: isset($data['reward_paid']) ? (float) $data['reward_paid'] : null,
            oracleResult: $data['oracle_result'] ?? null,
            resolvedAt: isset($data['resolved_at']) ? (int) $data['resolved_at'] : null,
            raw: $data,
        );
    }
}
