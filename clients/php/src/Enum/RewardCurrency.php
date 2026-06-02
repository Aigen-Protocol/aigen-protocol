<?php

declare(strict_types=1);

namespace Aigen\Oabp\Enum;

/**
 * Currency a mission reward is denominated in.
 *
 * AIGEN is the protocol's uncapped, off-chain reputation/points token.
 * USDC is an on-chain stablecoin used for real-value missions.
 */
enum RewardCurrency: string
{
    case Aigen = 'AIGEN';
    case Usdc = 'USDC';

    public static function tryFromApi(?string $value): ?self
    {
        if ($value === null) {
            return null;
        }

        return self::tryFrom($value);
    }

    /**
     * True for the off-chain reputation token (no real monetary value).
     */
    public function isPoints(): bool
    {
        return $this === self::Aigen;
    }
}
