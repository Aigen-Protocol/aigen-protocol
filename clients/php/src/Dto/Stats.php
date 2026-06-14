<?php

declare(strict_types=1);

namespace Aigen\Oabp\Dto;

/**
 * Protocol-wide statistics returned by `GET /api/stats`.
 *
 * @phpstan-type StatsShape array{
 *     resolved?: int|string|null,
 *     open?: int|string|null,
 *     lifetime_reward_aigen_paid?: int|float|string|null,
 *     ...
 * }
 */
final class Stats
{
    /**
     * @param array<string, mixed> $raw The untouched API payload.
     */
    public function __construct(
        public readonly int $resolved,
        public readonly int $open,
        public readonly float $lifetimeRewardAigenPaid,
        public readonly array $raw = [],
    ) {
    }

    /**
     * @param StatsShape $data
     */
    public static function fromArray(array $data): self
    {
        return new self(
            resolved: isset($data['resolved']) ? (int) $data['resolved'] : 0,
            open: isset($data['open']) ? (int) $data['open'] : 0,
            lifetimeRewardAigenPaid: isset($data['lifetime_reward_aigen_paid'])
                ? (float) $data['lifetime_reward_aigen_paid']
                : 0.0,
            raw: $data,
        );
    }

    public function total(): int
    {
        return $this->resolved + $this->open;
    }
}
