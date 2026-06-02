<?php

declare(strict_types=1);

namespace Aigen\Oabp\Dto;

/**
 * A deliverable submitted to a mission.
 *
 * @phpstan-type SubmissionShape array{
 *     id?: int|string|null,
 *     submitter_agent_id?: string|null,
 *     proof?: string|null,
 *     status?: string|null,
 *     verified?: bool|null,
 *     created_at?: int|string|null,
 *     ...
 * }
 */
final class Submission
{
    /**
     * @param array<string, mixed> $raw The untouched API payload.
     */
    public function __construct(
        public readonly ?string $id,
        public readonly ?string $submitterAgentId,
        /** Text or URL standing in for the deliverable. */
        public readonly ?string $proof,
        public readonly ?string $status,
        public readonly ?bool $verified,
        public readonly ?int $createdAt,
        public readonly array $raw = [],
    ) {
    }

    /**
     * @param SubmissionShape $data
     */
    public static function fromArray(array $data): self
    {
        return new self(
            id: isset($data['id']) ? (string) $data['id'] : null,
            submitterAgentId: isset($data['submitter_agent_id'])
                ? (string) $data['submitter_agent_id']
                : null,
            proof: isset($data['proof']) ? (string) $data['proof'] : null,
            status: isset($data['status']) ? (string) $data['status'] : null,
            verified: isset($data['verified']) ? (bool) $data['verified'] : null,
            createdAt: isset($data['created_at']) ? (int) $data['created_at'] : null,
            raw: $data,
        );
    }
}
