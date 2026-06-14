<?php

declare(strict_types=1);

namespace Aigen\Oabp;

use Aigen\Oabp\Dto\A2AResponse;
use Aigen\Oabp\Dto\CreateMissionRequest;
use Aigen\Oabp\Dto\Mission;
use Aigen\Oabp\Dto\Stats;
use Aigen\Oabp\Dto\SubmissionResult;
use Aigen\Oabp\Exception\ApiException;
use Aigen\Oabp\Exception\DecodingException;
use Aigen\Oabp\Exception\TransportException;
use GuzzleHttp\Client;
use GuzzleHttp\ClientInterface;
use GuzzleHttp\Exception\GuzzleException;
use GuzzleHttp\RequestOptions;
use Psr\Http\Message\ResponseInterface;

/**
 * Client for the OABP / AIGEN agent-bounty protocol.
 *
 * Wraps the documented HTTP API behind typed methods and DTOs:
 *  - list / create / fetch missions
 *  - submit deliverables
 *  - read protocol stats
 *  - call the A2A JSON-RPC endpoint and fetch the agent card / JWKS
 *
 * The transport is a Guzzle {@see ClientInterface}; inject a custom one
 * (e.g. with a {@see \GuzzleHttp\Handler\MockHandler}) for testing.
 *
 * @phpstan-import-type A2AResponseShape from A2AResponse
 */
final class OabpClient
{
    public const DEFAULT_BASE_URL = 'https://cryptogenesis.duckdns.org';

    public const USER_AGENT = 'oabp-php-sdk/1.0';

    private readonly ClientInterface $http;

    private readonly string $baseUrl;

    /** Auto-incrementing id for JSON-RPC requests. */
    private int $rpcId = 0;

    /**
     * @param array<string, mixed> $guzzleConfig Extra config merged into the
     *        default Guzzle client (ignored when $http is supplied).
     */
    public function __construct(
        string $baseUrl = self::DEFAULT_BASE_URL,
        ?string $apiKey = null,
        ?ClientInterface $http = null,
        float $timeout = 15.0,
        array $guzzleConfig = [],
    ) {
        $this->baseUrl = rtrim($baseUrl, '/');

        $headers = [
            'Accept' => 'application/json',
            'User-Agent' => self::USER_AGENT,
        ];
        if ($apiKey !== null && $apiKey !== '') {
            $headers['Authorization'] = 'Bearer ' . $apiKey;
        }

        $this->http = $http ?? new Client(array_merge([
            'base_uri' => $this->baseUrl . '/',
            'timeout' => $timeout,
            'http_errors' => false,
            'headers' => $headers,
        ], $guzzleConfig));
    }

    // ---------------------------------------------------------------------
    // Missions: list / create / get
    // ---------------------------------------------------------------------

    /**
     * `GET /api/missions` — list the open missions.
     *
     * @param array<string, scalar> $query Optional query string filters.
     *
     * @return list<Mission>
     *
     * @throws ApiException
     * @throws TransportException
     * @throws DecodingException
     */
    public function listMissions(array $query = []): array
    {
        /** @var array<int, mixed> $data */
        $data = $this->requestList('GET', '/api/missions', [
            RequestOptions::QUERY => $query,
        ]);

        $missions = [];
        foreach ($data as $row) {
            if (is_array($row)) {
                /** @var array<string, mixed> $row */
                $missions[] = Mission::fromArray($row);
            }
        }

        return $missions;
    }

    /**
     * `POST /api/missions` — create a mission. Returns the created mission.
     *
     * @throws ApiException
     * @throws TransportException
     * @throws DecodingException
     */
    public function createMission(CreateMissionRequest $request): Mission
    {
        $data = $this->requestObject('POST', '/api/missions', [
            RequestOptions::JSON => $request->toArray(),
        ]);

        // Some deployments wrap the created entity under a "mission" key.
        if (isset($data['mission']) && is_array($data['mission'])) {
            /** @var array<string, mixed> $inner */
            $inner = $data['mission'];

            return Mission::fromArray($inner);
        }

        return Mission::fromArray($data);
    }

    /**
     * `GET /api/missions/{id}` — fetch one mission with submissions & resolution.
     *
     * @throws ApiException
     * @throws TransportException
     * @throws DecodingException
     */
    public function getMission(string $id): Mission
    {
        $data = $this->requestObject('GET', '/api/missions/' . rawurlencode($id));

        if (isset($data['mission']) && is_array($data['mission'])) {
            /** @var array<string, mixed> $inner */
            $inner = $data['mission'];

            return Mission::fromArray($inner);
        }

        return Mission::fromArray($data);
    }

    // ---------------------------------------------------------------------
    // Submissions
    // ---------------------------------------------------------------------

    /**
     * `POST /missions/{id}/submit` — submit a deliverable to a mission.
     *
     * @param string $proof Text or a URL standing in for the deliverable.
     *
     * @throws ApiException
     * @throws TransportException
     * @throws DecodingException
     */
    public function submit(string $missionId, string $submitterAgentId, string $proof): SubmissionResult
    {
        $data = $this->requestObject('POST', '/missions/' . rawurlencode($missionId) . '/submit', [
            RequestOptions::JSON => [
                'submitter_agent_id' => $submitterAgentId,
                'proof' => $proof,
            ],
        ]);

        return SubmissionResult::fromArray($data);
    }

    // ---------------------------------------------------------------------
    // Stats
    // ---------------------------------------------------------------------

    /**
     * `GET /api/stats` — protocol-wide counters.
     *
     * @throws ApiException
     * @throws TransportException
     * @throws DecodingException
     */
    public function getStats(): Stats
    {
        return Stats::fromArray($this->requestObject('GET', '/api/stats'));
    }

    // ---------------------------------------------------------------------
    // A2A JSON-RPC + discovery
    // ---------------------------------------------------------------------

    /**
     * `POST /api/a2a` — low-level JSON-RPC 2.0 call.
     *
     * @param array<string, mixed> $params
     *
     * @throws ApiException
     * @throws TransportException
     * @throws DecodingException
     */
    public function a2a(string $method, array $params = []): A2AResponse
    {
        $payload = [
            'jsonrpc' => '2.0',
            'id' => ++$this->rpcId,
            'method' => $method,
            'params' => $params,
        ];

        $data = $this->requestObject('POST', '/api/a2a', [
            RequestOptions::JSON => $payload,
        ]);

        /** @var A2AResponseShape $data */
        return A2AResponse::fromArray($data);
    }

    /**
     * A2A `message/send` convenience wrapper.
     *
     * @param array<string, mixed> $message
     *
     * @throws ApiException
     * @throws TransportException
     * @throws DecodingException
     */
    public function a2aSendMessage(array $message): A2AResponse
    {
        return $this->a2a('message/send', ['message' => $message]);
    }

    /**
     * A2A `tasks/get` convenience wrapper.
     *
     * @throws ApiException
     * @throws TransportException
     * @throws DecodingException
     */
    public function a2aGetTask(string $taskId): A2AResponse
    {
        return $this->a2a('tasks/get', ['id' => $taskId]);
    }

    /**
     * A2A `tasks/list` convenience wrapper.
     *
     * @param array<string, mixed> $params
     *
     * @throws ApiException
     * @throws TransportException
     * @throws DecodingException
     */
    public function a2aListTasks(array $params = []): A2AResponse
    {
        return $this->a2a('tasks/list', $params);
    }

    /**
     * Fetch the ES256-signed agent card from `/.well-known/agent-card.json`.
     *
     * @return array<string, mixed>
     *
     * @throws ApiException
     * @throws TransportException
     * @throws DecodingException
     */
    public function getAgentCard(): array
    {
        return $this->requestObject('GET', '/.well-known/agent-card.json');
    }

    /**
     * Fetch the JWKS used to verify the agent card from `/.well-known/jwks.json`.
     *
     * @return array<string, mixed>
     *
     * @throws ApiException
     * @throws TransportException
     * @throws DecodingException
     */
    public function getJwks(): array
    {
        return $this->requestObject('GET', '/.well-known/jwks.json');
    }

    public function getBaseUrl(): string
    {
        return $this->baseUrl;
    }

    // ---------------------------------------------------------------------
    // Internal HTTP plumbing
    // ---------------------------------------------------------------------

    /**
     * Perform a request and decode a JSON object (associative array) body.
     *
     * @param array<string, mixed> $options
     *
     * @return array<string, mixed>
     *
     * @throws ApiException
     * @throws TransportException
     * @throws DecodingException
     */
    private function requestObject(string $method, string $path, array $options = []): array
    {
        $decoded = $this->decodeBody($this->send($method, $path, $options), $path);

        if (!is_array($decoded) || array_is_list($decoded)) {
            throw new DecodingException(sprintf(
                'Expected a JSON object from %s %s, got %s.',
                $method,
                $path,
                get_debug_type($decoded),
            ));
        }

        /** @var array<string, mixed> $decoded */
        return $decoded;
    }

    /**
     * Perform a request and decode a JSON array (list) body.
     *
     * @param array<string, mixed> $options
     *
     * @return array<int, mixed>
     *
     * @throws ApiException
     * @throws TransportException
     * @throws DecodingException
     */
    private function requestList(string $method, string $path, array $options = []): array
    {
        $decoded = $this->decodeBody($this->send($method, $path, $options), $path);

        // Tolerate an envelope like {"missions": [...]} as well as a bare array.
        if (is_array($decoded) && !array_is_list($decoded)) {
            foreach (['missions', 'data', 'items', 'results'] as $key) {
                if (isset($decoded[$key]) && is_array($decoded[$key])) {
                    /** @var array<int, mixed> $list */
                    $list = $decoded[$key];

                    return array_values($list);
                }
            }
        }

        if (!is_array($decoded) || !array_is_list($decoded)) {
            throw new DecodingException(sprintf(
                'Expected a JSON array from %s %s, got %s.',
                $method,
                $path,
                get_debug_type($decoded),
            ));
        }

        return $decoded;
    }

    /**
     * Send the request, mapping transport failures and non-2xx statuses to SDK
     * exceptions.
     *
     * @param array<string, mixed> $options
     *
     * @throws ApiException
     * @throws TransportException
     */
    private function send(string $method, string $path, array $options): ResponseInterface
    {
        try {
            $response = $this->http->request($method, ltrim($path, '/'), $options);
        } catch (GuzzleException $e) {
            throw new TransportException(
                sprintf('Transport error on %s %s: %s', $method, $path, $e->getMessage()),
                (int) $e->getCode(),
                $e,
            );
        }

        $status = $response->getStatusCode();
        if ($status < 200 || $status >= 300) {
            $raw = (string) $response->getBody();
            $body = $this->tryDecode($raw);

            $detail = '';
            if (is_array($body)) {
                foreach (['error', 'message', 'detail'] as $key) {
                    if (isset($body[$key]) && is_scalar($body[$key])) {
                        $detail = ': ' . (string) $body[$key];
                        break;
                    }
                }
            } elseif ($raw !== '') {
                $detail = ': ' . mb_substr($raw, 0, 300);
            }

            throw new ApiException(
                sprintf('HTTP %d on %s %s%s', $status, $method, $path, $detail),
                statusCode: $status,
                responseBody: (is_array($body) && !array_is_list($body)) ? $body : null,
                rawBody: $raw !== '' ? $raw : null,
            );
        }

        return $response;
    }

    /**
     * Decode a successful response body as JSON.
     *
     * @return array<mixed>
     *
     * @throws DecodingException
     */
    private function decodeBody(ResponseInterface $response, string $path): array
    {
        $raw = (string) $response->getBody();

        if (trim($raw) === '') {
            return [];
        }

        try {
            /** @var mixed $decoded */
            $decoded = json_decode($raw, true, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException $e) {
            throw new DecodingException(
                sprintf('Invalid JSON from %s: %s', $path, $e->getMessage()),
                0,
                $e,
            );
        }

        if (!is_array($decoded)) {
            throw new DecodingException(sprintf(
                'Expected JSON array/object from %s, got %s.',
                $path,
                get_debug_type($decoded),
            ));
        }

        return $decoded;
    }

    /**
     * Best-effort JSON decode that never throws (used for error bodies).
     *
     * @return array<mixed>|null
     */
    private function tryDecode(string $raw): ?array
    {
        if (trim($raw) === '') {
            return null;
        }

        $decoded = json_decode($raw, true);

        return is_array($decoded) ? $decoded : null;
    }
}
