<?php

declare(strict_types=1);

namespace Aigen\Oabp\Exception;

/**
 * Thrown when the HTTP request fails before a usable response is produced
 * (connection refused, DNS failure, timeout, TLS error, ...).
 */
final class TransportException extends \RuntimeException implements OabpException
{
}
