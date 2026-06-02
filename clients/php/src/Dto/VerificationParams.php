<?php

declare(strict_types=1);

namespace Aigen\Oabp\Dto;

/**
 * Parameters that drive how a mission is verified.
 *
 * Only the fields the protocol documents are typed; everything else is kept
 * verbatim in {@see VerificationParams::$extra} so the SDK never silently drops
 * data it does not yet model.
 *
 * @phpstan-type VerificationParamsShape array{
 *     regex?: string|null,
 *     oracle_description?: string|null,
 *     ...
 * }
 */
final class VerificationParams
{
    /**
     * @param array<string, mixed> $extra Any params not explicitly modelled.
     */
    public function __construct(
        /** Regex used by `first_valid_match` to content-address submissions. */
        public readonly ?string $regex = null,
        /** Free-text description an oracle mission verifies against. */
        public readonly ?string $oracleDescription = null,
        public readonly array $extra = [],
    ) {
    }

    /**
     * @param VerificationParamsShape $data
     */
    public static function fromArray(array $data): self
    {
        $known = ['regex', 'oracle_description'];

        /** @var array<string, mixed> $extra */
        $extra = array_diff_key($data, array_flip($known));

        return new self(
            regex: isset($data['regex']) ? (string) $data['regex'] : null,
            oracleDescription: isset($data['oracle_description'])
                ? (string) $data['oracle_description']
                : null,
            extra: $extra,
        );
    }

    /**
     * @return array<string, mixed>
     */
    public function toArray(): array
    {
        $out = $this->extra;

        if ($this->regex !== null) {
            $out['regex'] = $this->regex;
        }

        if ($this->oracleDescription !== null) {
            $out['oracle_description'] = $this->oracleDescription;
        }

        return $out;
    }
}
