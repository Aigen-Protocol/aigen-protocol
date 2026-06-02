<?php

declare(strict_types=1);

namespace Aigen\Oabp\Dto;

use Aigen\Oabp\Enum\RewardCurrency;

/**
 * A mission reward: an amount in a given currency (AIGEN or USDC).
 *
 * @phpstan-type RewardShape array{amount?: int|float|string|null, currency?: string|null}
 */
final class Reward
{
    public function __construct(
        public readonly float $amount,
        public readonly ?RewardCurrency $currency,
        /** Original currency string when it is not a known enum value. */
        public readonly ?string $rawCurrency = null,
    ) {
    }

    /**
     * @param RewardShape $data
     */
    public static function fromArray(array $data): self
    {
        $rawCurrency = isset($data['currency']) ? (string) $data['currency'] : null;

        return new self(
            amount: isset($data['amount']) ? (float) $data['amount'] : 0.0,
            currency: RewardCurrency::tryFromApi($rawCurrency),
            rawCurrency: $rawCurrency,
        );
    }

    public function currencyCode(): ?string
    {
        return $this->currency?->value ?? $this->rawCurrency;
    }

    /**
     * @return array{amount: float, currency: string|null}
     */
    public function toArray(): array
    {
        return [
            'amount' => $this->amount,
            'currency' => $this->currencyCode(),
        ];
    }

    public function __toString(): string
    {
        $code = $this->currencyCode() ?? '?';

        return rtrim(rtrim(sprintf('%.8f', $this->amount), '0'), '.') . ' ' . $code;
    }
}
