<?php

declare(strict_types=1);

namespace Aigen\Oabp\Tests;

use Aigen\Oabp\Dto\CreateMissionRequest;
use Aigen\Oabp\Dto\Mission;
use Aigen\Oabp\Dto\Reward;
use Aigen\Oabp\Dto\VerificationParams;
use Aigen\Oabp\Enum\RewardCurrency;
use Aigen\Oabp\Enum\VerificationType;
use PHPUnit\Framework\TestCase;

final class DtoTest extends TestCase
{
    public function testVerificationTypeMapping(): void
    {
        self::assertSame(VerificationType::FirstValidMatch, VerificationType::tryFromApi('first_valid_match'));
        self::assertSame(VerificationType::Oracle, VerificationType::tryFromApi('oracle'));
        self::assertSame(VerificationType::PeerVote, VerificationType::tryFromApi('peer_vote'));
        self::assertSame(VerificationType::CreatorJudges, VerificationType::tryFromApi('creator_judges'));
        self::assertNull(VerificationType::tryFromApi('something_new'));
        self::assertNull(VerificationType::tryFromApi(null));
    }

    public function testVerificationTypeIsAutomatic(): void
    {
        self::assertTrue(VerificationType::FirstValidMatch->isAutomatic());
        self::assertTrue(VerificationType::Oracle->isAutomatic());
        self::assertFalse(VerificationType::PeerVote->isAutomatic());
        self::assertFalse(VerificationType::CreatorJudges->isAutomatic());
    }

    public function testRewardCurrency(): void
    {
        self::assertSame(RewardCurrency::Aigen, RewardCurrency::tryFromApi('AIGEN'));
        self::assertSame(RewardCurrency::Usdc, RewardCurrency::tryFromApi('USDC'));
        self::assertNull(RewardCurrency::tryFromApi('BTC'));
        self::assertTrue(RewardCurrency::Aigen->isPoints());
        self::assertFalse(RewardCurrency::Usdc->isPoints());
    }

    public function testRewardFromArrayAndToString(): void
    {
        $reward = Reward::fromArray(['amount' => '100.5', 'currency' => 'AIGEN']);
        self::assertSame(100.5, $reward->amount);
        self::assertSame(RewardCurrency::Aigen, $reward->currency);
        self::assertSame('AIGEN', $reward->currencyCode());
        self::assertSame('100.5 AIGEN', (string) $reward);

        // Unknown currency is preserved as raw.
        $unknown = Reward::fromArray(['amount' => 1, 'currency' => 'BTC']);
        self::assertNull($unknown->currency);
        self::assertSame('BTC', $unknown->currencyCode());
        self::assertSame('1 BTC', (string) $unknown);
    }

    public function testVerificationParamsRoundTripPreservesExtra(): void
    {
        $params = VerificationParams::fromArray([
            'regex' => '^x$',
            'oracle_description' => 'safety review',
            'min_confidence' => 0.9,
        ]);

        self::assertSame('^x$', $params->regex);
        self::assertSame('safety review', $params->oracleDescription);
        self::assertSame(['min_confidence' => 0.9], $params->extra);

        $array = $params->toArray();
        self::assertSame('^x$', $array['regex']);
        self::assertSame('safety review', $array['oracle_description']);
        self::assertSame(0.9, $array['min_confidence']);
    }

    public function testMissionExpiryAndOpenInference(): void
    {
        $mission = Mission::fromArray([
            'id' => '1',
            'title' => 't',
            'deadline' => 1000,
            // No explicit status -> open inferred from missing resolution.
        ]);

        self::assertTrue($mission->isOpen());
        self::assertTrue($mission->isExpired(now: 2000));
        self::assertFalse($mission->isExpired(now: 500));

        $noDeadline = Mission::fromArray(['id' => '2', 'title' => 't']);
        self::assertFalse($noDeadline->isExpired(now: PHP_INT_MAX));
    }

    public function testCreateMissionRequestFirstValidMatchBuilder(): void
    {
        $req = CreateMissionRequest::firstValidMatch(
            creatorAgentId: 'agent-1',
            title: 'T',
            description: 'D',
            rewardAmount: 10.0,
            rewardCurrency: RewardCurrency::Usdc,
            regex: '^OK$',
            deadlineHours: 24,
        );

        $array = $req->toArray();
        self::assertSame('agent-1', $array['creator_agent_id']);
        self::assertSame('USDC', $array['reward_currency']);
        self::assertSame('first_valid_match', $array['verification_type']);
        self::assertSame(['regex' => '^OK$'], $array['verification_params']);
        self::assertSame(24, $array['deadline_hours']);
    }

    public function testCreateMissionRequestAcceptsRawParamsArray(): void
    {
        $req = new CreateMissionRequest(
            creatorAgentId: 'a',
            title: 'T',
            description: 'D',
            rewardAmount: 1.0,
            rewardCurrency: RewardCurrency::Aigen,
            verificationType: VerificationType::PeerVote,
            verificationParams: ['quorum' => 3, 'window_hours' => 12],
            deadlineHours: 6,
        );

        $array = $req->toArray();
        self::assertSame(['quorum' => 3, 'window_hours' => 12], $array['verification_params']);
        self::assertSame('peer_vote', $array['verification_type']);
    }
}
