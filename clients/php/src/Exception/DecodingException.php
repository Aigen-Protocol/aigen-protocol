<?php

declare(strict_types=1);

namespace Aigen\Oabp\Exception;

/**
 * Thrown when a 2xx response body cannot be decoded as the expected JSON shape
 * (malformed JSON, or a top-level type that is not what the endpoint promises).
 */
final class DecodingException extends \RuntimeException implements OabpException
{
}
