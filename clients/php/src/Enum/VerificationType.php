<?php

declare(strict_types=1);

namespace Aigen\Oabp\Enum;

/**
 * How a mission's submissions are verified before a reward is paid.
 *
 * Verification in OABP is permissionless. Each value maps 1:1 to the
 * `verification_type` field accepted/returned by the protocol API.
 */
enum VerificationType: string
{
    /**
     * Content-addressed verification. The first submission whose `proof`
     * matches `verification_params.regex` wins. Deterministic, no oracle.
     */
    case FirstValidMatch = 'first_valid_match';

    /**
     * Oracle-backed verification (no code execution). The protocol checks the
     * deliverable for real:
     *  - GoPlus token-security for "safety review" missions;
     *  - GitHub REST for "repo deliverable" missions.
     */
    case Oracle = 'oracle';

    /**
     * Submissions are ranked by a vote among participating peers.
     */
    case PeerVote = 'peer_vote';

    /**
     * The mission creator judges submissions and selects the winner.
     */
    case CreatorJudges = 'creator_judges';

    /**
     * Build from a raw API string, tolerating unknown/future values by
     * returning null instead of throwing.
     */
    public static function tryFromApi(?string $value): ?self
    {
        if ($value === null) {
            return null;
        }

        return self::tryFrom($value);
    }

    /**
     * True when the protocol resolves the mission automatically (no humans).
     */
    public function isAutomatic(): bool
    {
        return match ($this) {
            self::FirstValidMatch, self::Oracle => true,
            self::PeerVote, self::CreatorJudges => false,
        };
    }

    /**
     * Human-readable label, handy for CLIs and logs.
     */
    public function label(): string
    {
        return match ($this) {
            self::FirstValidMatch => 'First valid match (content-addressed)',
            self::Oracle => 'Oracle (GoPlus / GitHub)',
            self::PeerVote => 'Peer vote',
            self::CreatorJudges => 'Creator judges',
        };
    }
}
