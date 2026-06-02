<?php

declare(strict_types=1);

namespace Aigen\Oabp\Dto;

/**
 * Result of `POST /missions/{id}/submit`.
 *
 * The protocol may resolve a mission synchronously on submit (e.g. a
 * `first_valid_match` whose regex matches, or an oracle that verifies on the
 * spot), so this wraps both the accepted submission and any resolution.
 *
 * @phpstan-import-type SubmissionShape from Submission
 * @phpstan-import-type ResolutionShape from Resolution
 *
 * @phpstan-type SubmissionResultShape array{
 *     accepted?: bool|null,
 *     verified?: bool|null,
 *     submission?: SubmissionShape|null,
 *     resolution?: ResolutionShape|null,
 *     message?: string|null,
 *     ...
 * }
 */
final class SubmissionResult
{
    /**
     * @param array<string, mixed> $raw The untouched API payload.
     */
    public function __construct(
        public readonly bool $accepted,
        public readonly ?bool $verified,
        public readonly ?Submission $submission,
        public readonly ?Resolution $resolution,
        public readonly ?string $message,
        public readonly array $raw = [],
    ) {
    }

    /**
     * @param SubmissionResultShape $data
     */
    public static function fromArray(array $data): self
    {
        $submission = null;
        if (isset($data['submission']) && is_array($data['submission'])) {
            /** @var SubmissionShape $subData */
            $subData = $data['submission'];
            $submission = Submission::fromArray($subData);
        }

        $resolution = null;
        if (isset($data['resolution']) && is_array($data['resolution']) && $data['resolution'] !== []) {
            /** @var ResolutionShape $resData */
            $resData = $data['resolution'];
            $resolution = Resolution::fromArray($resData);
        }

        // The API may not echo an explicit "accepted" flag; infer acceptance
        // from the presence of a submission object or a truthy verified flag.
        $accepted = isset($data['accepted'])
            ? (bool) $data['accepted']
            : ($submission !== null || ($data['verified'] ?? false) === true);

        return new self(
            accepted: $accepted,
            verified: isset($data['verified']) ? (bool) $data['verified'] : null,
            submission: $submission,
            resolution: $resolution,
            message: isset($data['message']) ? (string) $data['message'] : null,
            raw: $data,
        );
    }

    /**
     * True when this submission won the mission outright.
     */
    public function isWinner(): bool
    {
        return $this->resolution !== null
            && $this->submission !== null
            && $this->resolution->winningSubmissionId !== null
            && $this->resolution->winningSubmissionId === $this->submission->id;
    }
}
