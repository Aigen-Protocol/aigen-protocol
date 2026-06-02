<?php

declare(strict_types=1);

namespace Aigen\Oabp\Tests;

use Aigen\Oabp\Dto\CreateMissionRequest;
use Aigen\Oabp\Dto\Mission;
use Aigen\Oabp\Enum\RewardCurrency;
use Aigen\Oabp\Enum\VerificationType;
use Aigen\Oabp\Exception\ApiException;
use Aigen\Oabp\Exception\DecodingException;
use Aigen\Oabp\Exception\TransportException;
use Aigen\Oabp\OabpClient;
use GuzzleHttp\Client;
use GuzzleHttp\Exception\ConnectException;
use GuzzleHttp\Handler\MockHandler;
use GuzzleHttp\HandlerStack;
use GuzzleHttp\Middleware;
use GuzzleHttp\Psr7\Request;
use GuzzleHttp\Psr7\Response;
use PHPUnit\Framework\TestCase;
use Psr\Http\Message\RequestInterface;

final class OabpClientTest extends TestCase
{
    /** @var list<array{request: RequestInterface, ...}> */
    private array $history = [];

    private MockHandler $mock;

    protected function setUp(): void
    {
        $this->history = [];
        $this->mock = new MockHandler();
    }

    private function makeClient(): OabpClient
    {
        $stack = HandlerStack::create($this->mock);
        $stack->push(Middleware::history($this->history));

        $guzzle = new Client([
            'handler' => $stack,
            'base_uri' => OabpClient::DEFAULT_BASE_URL . '/',
            'http_errors' => false,
        ]);

        return new OabpClient(http: $guzzle);
    }

    /**
     * @param array<mixed> $payload
     */
    private function jsonResponse(array $payload, int $status = 200): Response
    {
        return new Response($status, ['Content-Type' => 'application/json'], (string) json_encode($payload));
    }

    private function lastRequest(): RequestInterface
    {
        $entry = end($this->history);
        self::assertIsArray($entry);

        return $entry['request'];
    }

    public function testListMissionsParsesArray(): void
    {
        $this->mock->append($this->jsonResponse([
            [
                'id' => '42',
                'title' => 'Find the magic string',
                'description' => 'Submit a proof that matches.',
                'reward' => ['amount' => 100, 'currency' => 'AIGEN'],
                'verification_type' => 'first_valid_match',
                'verification_params' => ['regex' => '^MAGIC-[0-9]+$'],
                'deadline' => 1893456000,
                'status' => 'open',
                'submissions' => [],
            ],
            [
                'id' => '43',
                'title' => 'Repo deliverable',
                'reward' => ['amount' => 5, 'currency' => 'USDC'],
                'verification_type' => 'oracle',
                'verification_params' => ['oracle_description' => 'repo deliverable'],
                'deadline' => 1893456000,
                'status' => 'open',
                'submissions' => [
                    ['id' => '1', 'submitter_agent_id' => 'agent-x', 'proof' => 'https://github.com/a/b'],
                ],
            ],
        ]));

        $client = $this->makeClient();
        $missions = $client->listMissions(['status' => 'open']);

        self::assertCount(2, $missions);
        self::assertContainsOnlyInstancesOf(Mission::class, $missions);

        $first = $missions[0];
        self::assertSame('42', $first->id);
        self::assertSame('Find the magic string', $first->title);
        self::assertSame(VerificationType::FirstValidMatch, $first->verificationType);
        self::assertNotNull($first->verificationParams);
        self::assertSame('^MAGIC-[0-9]+$', $first->verificationParams->regex);
        self::assertNotNull($first->reward);
        self::assertSame(100.0, $first->reward->amount);
        self::assertSame(RewardCurrency::Aigen, $first->reward->currency);
        self::assertTrue($first->isOpen());
        self::assertSame(0, $first->submissionCount());

        $second = $missions[1];
        self::assertSame(VerificationType::Oracle, $second->verificationType);
        self::assertNotNull($second->reward);
        self::assertSame(RewardCurrency::Usdc, $second->reward->currency);
        self::assertSame(1, $second->submissionCount());
        self::assertSame('agent-x', $second->submissions[0]->submitterAgentId);

        // Verify the request was shaped correctly.
        $req = $this->lastRequest();
        self::assertSame('GET', $req->getMethod());
        self::assertSame('/api/missions', $req->getUri()->getPath());
        self::assertStringContainsString('status=open', $req->getUri()->getQuery());
    }

    public function testListMissionsAcceptsEnvelope(): void
    {
        $this->mock->append($this->jsonResponse([
            'missions' => [
                ['id' => '7', 'title' => 'Enveloped', 'verification_type' => 'peer_vote'],
            ],
        ]));

        $missions = $this->makeClient()->listMissions();

        self::assertCount(1, $missions);
        self::assertSame('7', $missions[0]->id);
        self::assertSame(VerificationType::PeerVote, $missions[0]->verificationType);
    }

    public function testCreateMissionSendsCorrectBody(): void
    {
        $this->mock->append($this->jsonResponse([
            'id' => '99',
            'title' => 'Safety review of token',
            'verification_type' => 'oracle',
            'verification_params' => ['oracle_description' => 'safety review'],
            'reward' => ['amount' => 250, 'currency' => 'AIGEN'],
            'status' => 'open',
            'creator_agent_id' => 'creator-1',
        ], 201));

        $client = $this->makeClient();

        $request = CreateMissionRequest::oracle(
            creatorAgentId: 'creator-1',
            title: 'Safety review of token',
            description: 'Run GoPlus on 0xabc...',
            rewardAmount: 250.0,
            rewardCurrency: RewardCurrency::Aigen,
            oracleDescription: 'safety review',
            deadlineHours: 48,
        );

        $mission = $client->createMission($request);

        self::assertSame('99', $mission->id);
        self::assertSame(VerificationType::Oracle, $mission->verificationType);
        self::assertSame('creator-1', $mission->creatorAgentId);

        $req = $this->lastRequest();
        self::assertSame('POST', $req->getMethod());
        self::assertSame('/api/missions', $req->getUri()->getPath());

        /** @var array<string, mixed> $body */
        $body = json_decode((string) $req->getBody(), true);
        self::assertSame('creator-1', $body['creator_agent_id']);
        self::assertSame('Safety review of token', $body['title']);
        // JSON collapses 250.0 to 250, so compare numerically rather than by type.
        self::assertEqualsWithDelta(250.0, $body['reward_amount'], 1e-9);
        self::assertSame('AIGEN', $body['reward_currency']);
        self::assertSame('oracle', $body['verification_type']);
        self::assertSame(48, $body['deadline_hours']);
        self::assertIsArray($body['verification_params']);
        self::assertSame('safety review', $body['verification_params']['oracle_description']);
    }

    public function testCreateMissionUnwrapsEnvelope(): void
    {
        $this->mock->append($this->jsonResponse([
            'mission' => ['id' => '100', 'title' => 'Wrapped', 'verification_type' => 'creator_judges'],
        ], 201));

        $request = CreateMissionRequest::firstValidMatch(
            creatorAgentId: 'c',
            title: 'Wrapped',
            description: 'd',
            rewardAmount: 1.0,
            rewardCurrency: RewardCurrency::Aigen,
            regex: '.*',
            deadlineHours: 1,
        );

        $mission = $this->makeClient()->createMission($request);
        self::assertSame('100', $mission->id);
        self::assertSame(VerificationType::CreatorJudges, $mission->verificationType);
    }

    public function testGetMission(): void
    {
        $this->mock->append($this->jsonResponse([
            'id' => '42',
            'title' => 'Detail',
            'verification_type' => 'first_valid_match',
            'submissions' => [
                ['id' => '11', 'submitter_agent_id' => 'a1', 'proof' => 'MAGIC-7', 'verified' => true],
            ],
            'resolution' => [
                'winner_agent_id' => 'a1',
                'winning_submission_id' => '11',
                'reward_paid' => 99.5,
                'resolved_at' => 1893456001,
            ],
        ]));

        $mission = $this->makeClient()->getMission('42');

        self::assertSame('42', $mission->id);
        self::assertSame(1, $mission->submissionCount());
        self::assertTrue($mission->submissions[0]->verified);
        self::assertNotNull($mission->resolution);
        self::assertSame('a1', $mission->resolution->winnerAgentId);
        self::assertSame('11', $mission->resolution->winningSubmissionId);
        self::assertSame(99.5, $mission->resolution->rewardPaid);
        self::assertFalse($mission->isOpen());

        self::assertSame('/api/missions/42', $this->lastRequest()->getUri()->getPath());
    }

    public function testGetMissionIdIsUrlEncoded(): void
    {
        $this->mock->append($this->jsonResponse(['id' => 'a/b c', 'title' => 'x']));

        $this->makeClient()->getMission('a/b c');

        // rawurlencode turns "a/b c" into "a%2Fb%20c".
        self::assertSame('/api/missions/a%2Fb%20c', $this->lastRequest()->getUri()->getPath());
    }

    public function testSubmitWinningDeliverable(): void
    {
        $this->mock->append($this->jsonResponse([
            'accepted' => true,
            'verified' => true,
            'submission' => ['id' => '500', 'submitter_agent_id' => 'me', 'proof' => 'MAGIC-42'],
            'resolution' => ['winner_agent_id' => 'me', 'winning_submission_id' => '500', 'reward_paid' => 100],
            'message' => 'Mission resolved on submit',
        ]));

        $result = $this->makeClient()->submit('42', 'me', 'MAGIC-42');

        self::assertTrue($result->accepted);
        self::assertTrue($result->verified);
        self::assertNotNull($result->submission);
        self::assertSame('500', $result->submission->id);
        self::assertNotNull($result->resolution);
        self::assertTrue($result->isWinner());
        self::assertSame('Mission resolved on submit', $result->message);

        $req = $this->lastRequest();
        self::assertSame('POST', $req->getMethod());
        self::assertSame('/missions/42/submit', $req->getUri()->getPath());

        /** @var array<string, mixed> $body */
        $body = json_decode((string) $req->getBody(), true);
        self::assertSame('me', $body['submitter_agent_id']);
        self::assertSame('MAGIC-42', $body['proof']);
    }

    public function testSubmitAcceptedButNotWinner(): void
    {
        $this->mock->append($this->jsonResponse([
            'submission' => ['id' => '501', 'submitter_agent_id' => 'me', 'proof' => 'nope'],
        ]));

        $result = $this->makeClient()->submit('42', 'me', 'nope');

        // Acceptance inferred from presence of the submission object.
        self::assertTrue($result->accepted);
        self::assertFalse($result->isWinner());
        self::assertNull($result->resolution);
    }

    public function testGetStats(): void
    {
        $this->mock->append($this->jsonResponse([
            'resolved' => 12,
            'open' => 5,
            'lifetime_reward_aigen_paid' => 108000.5,
        ]));

        $stats = $this->makeClient()->getStats();

        self::assertSame(12, $stats->resolved);
        self::assertSame(5, $stats->open);
        self::assertSame(108000.5, $stats->lifetimeRewardAigenPaid);
        self::assertSame(17, $stats->total());

        self::assertSame('/api/stats', $this->lastRequest()->getUri()->getPath());
    }

    public function testA2ASendMessageSuccess(): void
    {
        $this->mock->append($this->jsonResponse([
            'jsonrpc' => '2.0',
            'id' => 1,
            'result' => ['taskId' => 'task-1', 'status' => 'submitted'],
        ]));

        $resp = $this->makeClient()->a2aSendMessage([
            'role' => 'user',
            'parts' => [['kind' => 'text', 'text' => 'list open missions']],
        ]);

        self::assertFalse($resp->isError());
        /** @var array<string, mixed> $result */
        $result = $resp->resultOrThrow();
        self::assertSame('task-1', $result['taskId']);

        $req = $this->lastRequest();
        self::assertSame('/api/a2a', $req->getUri()->getPath());

        /** @var array<string, mixed> $body */
        $body = json_decode((string) $req->getBody(), true);
        self::assertSame('2.0', $body['jsonrpc']);
        self::assertSame('message/send', $body['method']);
        self::assertSame(1, $body['id']);
        self::assertArrayHasKey('message', $body['params']);
    }

    public function testA2AErrorIsExposedAndThrowsOnResultOrThrow(): void
    {
        $this->mock->append($this->jsonResponse([
            'jsonrpc' => '2.0',
            'id' => 1,
            'error' => ['code' => -32601, 'message' => 'Method not found'],
        ]));

        $resp = $this->makeClient()->a2a('bogus/method');

        self::assertTrue($resp->isError());
        self::assertSame(-32601, $resp->errorCode());
        self::assertSame('Method not found', $resp->errorMessage());

        $this->expectException(ApiException::class);
        $this->expectExceptionMessage('Method not found');
        $resp->resultOrThrow();
    }

    public function testRpcIdIncrements(): void
    {
        $this->mock->append(
            $this->jsonResponse(['jsonrpc' => '2.0', 'id' => 1, 'result' => []]),
            $this->jsonResponse(['jsonrpc' => '2.0', 'id' => 2, 'result' => []]),
        );

        $client = $this->makeClient();
        $client->a2aListTasks();
        $client->a2aGetTask('t1');

        /** @var array{request: RequestInterface} $firstEntry */
        $firstEntry = $this->history[0];
        /** @var array{request: RequestInterface} $secondEntry */
        $secondEntry = $this->history[1];

        /** @var array<string, mixed> $b1 */
        $b1 = json_decode((string) $firstEntry['request']->getBody(), true);
        /** @var array<string, mixed> $b2 */
        $b2 = json_decode((string) $secondEntry['request']->getBody(), true);

        self::assertSame(1, $b1['id']);
        self::assertSame('tasks/list', $b1['method']);
        self::assertSame(2, $b2['id']);
        self::assertSame('tasks/get', $b2['method']);
        self::assertSame(['id' => 't1'], $b2['params']);
    }

    public function testGetAgentCard(): void
    {
        $this->mock->append($this->jsonResponse([
            'name' => 'AIGEN Protocol Agent',
            'url' => 'https://cryptogenesis.duckdns.org/api/a2a',
            'capabilities' => ['streaming' => false],
        ]));

        $card = $this->makeClient()->getAgentCard();

        self::assertSame('AIGEN Protocol Agent', $card['name']);
        self::assertSame('/.well-known/agent-card.json', $this->lastRequest()->getUri()->getPath());
    }

    public function testGetJwks(): void
    {
        $this->mock->append($this->jsonResponse([
            'keys' => [['kty' => 'EC', 'crv' => 'P-256', 'kid' => 'k1']],
        ]));

        $jwks = $this->makeClient()->getJwks();

        self::assertArrayHasKey('keys', $jwks);
        self::assertSame('/.well-known/jwks.json', $this->lastRequest()->getUri()->getPath());
    }

    public function testApiExceptionOnHttp404WithJsonBody(): void
    {
        $this->mock->append($this->jsonResponse(['error' => 'mission not found'], 404));

        try {
            $this->makeClient()->getMission('does-not-exist');
            self::fail('Expected ApiException');
        } catch (ApiException $e) {
            self::assertSame(404, $e->getStatusCode());
            self::assertTrue($e->isClientError());
            self::assertFalse($e->isServerError());
            self::assertStringContainsString('mission not found', $e->getMessage());
            self::assertSame('mission not found', $e->getResponseBody()['error'] ?? null);
        }
    }

    public function testApiExceptionOnHttp500(): void
    {
        $this->mock->append(new Response(500, [], 'internal error'));

        try {
            $this->makeClient()->getStats();
            self::fail('Expected ApiException');
        } catch (ApiException $e) {
            self::assertSame(500, $e->getStatusCode());
            self::assertTrue($e->isServerError());
            self::assertSame('internal error', $e->getRawBody());
        }
    }

    public function testTransportExceptionOnConnectionFailure(): void
    {
        $this->mock->append(new ConnectException('Connection refused', new Request('GET', 'test')));

        $this->expectException(TransportException::class);
        $this->makeClient()->getStats();
    }

    public function testDecodingExceptionOnInvalidJson(): void
    {
        $this->mock->append(new Response(200, ['Content-Type' => 'application/json'], '{not valid json'));

        $this->expectException(DecodingException::class);
        $this->makeClient()->getStats();
    }

    public function testDecodingExceptionWhenObjectExpectedButArrayReturned(): void
    {
        // /api/stats must be an object; returning a bare list is a contract break.
        $this->mock->append($this->jsonResponse([1, 2, 3]));

        $this->expectException(DecodingException::class);
        $this->makeClient()->getStats();
    }

    public function testDecodingExceptionWhenListExpectedButScalarObject(): void
    {
        // listMissions tolerates envelopes, but a plain object with no list key fails.
        $this->mock->append($this->jsonResponse(['unexpected' => 'shape']));

        $this->expectException(DecodingException::class);
        $this->makeClient()->listMissions();
    }
}
