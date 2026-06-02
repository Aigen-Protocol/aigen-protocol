<?php

declare(strict_types=1);

namespace Aigen\Oabp\Exception;

/**
 * Thrown when the API returns a non-2xx HTTP status.
 *
 * Carries the status code and, when the body is JSON, the decoded error payload
 * so callers can inspect protocol-level error details.
 */
final class ApiException extends \RuntimeException implements OabpException
{
    /**
     * @param array<string, mixed>|null $responseBody Decoded JSON error body, if any.
     */
    public function __construct(
        string $message,
        private readonly int $statusCode,
        private readonly ?array $responseBody = null,
        private readonly ?string $rawBody = null,
        ?\Throwable $previous = null,
    ) {
        parent::__construct($message, $statusCode, $previous);
    }

    public function getStatusCode(): int
    {
        return $this->statusCode;
    }

    /**
     * @return array<string, mixed>|null
     */
    public function getResponseBody(): ?array
    {
        return $this->responseBody;
    }

    public function getRawBody(): ?string
    {
        return $this->rawBody;
    }

    public function isClientError(): bool
    {
        return $this->statusCode >= 400 && $this->statusCode < 500;
    }

    public function isServerError(): bool
    {
        return $this->statusCode >= 500;
    }
}
