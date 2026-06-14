<?php

declare(strict_types=1);

namespace Aigen\Oabp\Exception;

/**
 * Marker interface implemented by every exception this SDK throws, so callers
 * can `catch (OabpException $e)` to trap anything originating in the client.
 */
interface OabpException extends \Throwable
{
}
