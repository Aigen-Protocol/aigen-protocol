<?php

declare(strict_types=1);

namespace Aigen\Oabp\Dto;

use Aigen\Oabp\Exception\ApiException;

/**
 * A JSON-RPC 2.0 response from the A2A endpoint (`POST /api/a2a`).
 *
 * @phpstan-type A2AResponseShape array{
 *     jsonrpc?: string,
 *     id?: int|string|null,
 *     result?: mixed,
 *     error?: array{code?: int, message?: string, data?: mixed}|null
 * }
 */
final class A2AResponse
{
    /**
     * @param mixed                                                  $result Present on success.
     * @param array{code?: int, message?: string, data?: mixed}|null $error  Present on failure.
     */
    public function __construct(
        public readonly string $jsonrpc,
        public readonly int|string|null $id,
        public readonly mixed $result,
        public readonly ?array $error,
    ) {
    }

    /**
     * @param A2AResponseShape $data
     */
    public static function fromArray(array $data): self
    {
        /** @var array{code?: int, message?: string, data?: mixed}|null $error */
        $error = (isset($data['error']) && is_array($data['error'])) ? $data['error'] : null;

        return new self(
            jsonrpc: isset($data['jsonrpc']) ? (string) $data['jsonrpc'] : '2.0',
            id: $data['id'] ?? null,
            result: $data['result'] ?? null,
            error: $error,
        );
    }

    public function isError(): bool
    {
        return $this->error !== null;
    }

    public function errorMessage(): ?string
    {
        if ($this->error === null) {
            return null;
        }

        return isset($this->error['message']) ? (string) $this->error['message'] : 'unknown JSON-RPC error';
    }

    public function errorCode(): ?int
    {
        if ($this->error === null) {
            return null;
        }

        return isset($this->error['code']) ? (int) $this->error['code'] : null;
    }

    /**
     * Return the result, or throw if this response is a JSON-RPC error.
     *
     * @throws ApiException
     */
    public function resultOrThrow(): mixed
    {
        if ($this->isError()) {
            $code = $this->errorCode() ?? -1;
            throw new ApiException(
                sprintf('A2A JSON-RPC error %d: %s', $code, (string) $this->errorMessage()),
                statusCode: 200,
                responseBody: $this->error,
            );
        }

        return $this->result;
    }
}
