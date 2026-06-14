<?php

declare(strict_types=1);

namespace Aigen\Oabp\Dto;

use Aigen\Oabp\Enum\VerificationType;

/**
 * An open or resolved bounty mission.
 *
 * @phpstan-import-type RewardShape from Reward
 * @phpstan-import-type VerificationParamsShape from VerificationParams
 * @phpstan-import-type SubmissionShape from Submission
 * @phpstan-import-type ResolutionShape from Resolution
 *
 * @phpstan-type MissionShape array{
 *     id?: int|string|null,
 *     title?: string|null,
 *     description?: string|null,
 *     reward?: RewardShape|null,
 *     verification_type?: string|null,
 *     verification_params?: VerificationParamsShape|null,
 *     deadline?: int|string|null,
 *     status?: string|null,
 *     submissions?: list<SubmissionShape>|null,
 *     resolution?: ResolutionShape|null,
 *     creator_agent_id?: string|null,
 *     ...
 * }
 */
final class Mission
{
    /**
     * @param list<Submission>     $submissions
     * @param array<string, mixed> $raw The untouched API payload.
     */
    public function __construct(
        public readonly ?string $id,
        public readonly ?string $title,
        public readonly ?string $description,
        public readonly ?Reward $reward,
        public readonly ?VerificationType $verificationType,
        public readonly ?VerificationParams $verificationParams,
        /** Unix timestamp (seconds) after which the mission is closed. */
        public readonly ?int $deadline,
        public readonly ?string $status,
        public readonly array $submissions,
        public readonly ?Resolution $resolution,
        public readonly ?string $creatorAgentId,
        public readonly array $raw = [],
    ) {
    }

    /**
     * @param MissionShape $data
     */
    public static function fromArray(array $data): self
    {
        $submissions = [];
        if (isset($data['submissions']) && is_array($data['submissions'])) {
            foreach ($data['submissions'] as $sub) {
                if (is_array($sub)) {
                    /** @var SubmissionShape $sub */
                    $submissions[] = Submission::fromArray($sub);
                }
            }
        }

        $reward = null;
        if (isset($data['reward']) && is_array($data['reward'])) {
            /** @var RewardShape $rewardData */
            $rewardData = $data['reward'];
            $reward = Reward::fromArray($rewardData);
        }

        $params = null;
        if (isset($data['verification_params']) && is_array($data['verification_params'])) {
            /** @var VerificationParamsShape $paramsData */
            $paramsData = $data['verification_params'];
            $params = VerificationParams::fromArray($paramsData);
        }

        $resolution = null;
        if (isset($data['resolution']) && is_array($data['resolution']) && $data['resolution'] !== []) {
            /** @var ResolutionShape $resData */
            $resData = $data['resolution'];
            $resolution = Resolution::fromArray($resData);
        }

        return new self(
            id: isset($data['id']) ? (string) $data['id'] : null,
            title: isset($data['title']) ? (string) $data['title'] : null,
            description: isset($data['description']) ? (string) $data['description'] : null,
            reward: $reward,
            verificationType: VerificationType::tryFromApi(
                isset($data['verification_type']) ? (string) $data['verification_type'] : null
            ),
            verificationParams: $params,
            deadline: isset($data['deadline']) ? (int) $data['deadline'] : null,
            status: isset($data['status']) ? (string) $data['status'] : null,
            submissions: $submissions,
            resolution: $resolution,
            creatorAgentId: isset($data['creator_agent_id'])
                ? (string) $data['creator_agent_id']
                : null,
            raw: $data,
        );
    }

    public function isOpen(): bool
    {
        if ($this->status !== null) {
            return strtolower($this->status) === 'open';
        }

        return $this->resolution === null;
    }

    /**
     * True when the deadline (if known) is in the past.
     */
    public function isExpired(?int $now = null): bool
    {
        if ($this->deadline === null) {
            return false;
        }

        return $this->deadline < ($now ?? time());
    }

    public function submissionCount(): int
    {
        return count($this->submissions);
    }
}
