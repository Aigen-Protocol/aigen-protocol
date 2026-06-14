/**
 * Error types thrown by the OABP SDK. All extend the native `Error` and carry
 * structured context so callers can branch on failure cause.
 */

/** Base class for every error the SDK throws. */
export class OabpError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "OabpError";
    // Restore prototype chain for ES5 targets / transpiled output.
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/**
 * Thrown when the API responds with a non-2xx status. Exposes the HTTP status,
 * the raw response body, and a parsed body when the payload was JSON.
 */
export class OabpApiError extends OabpError {
  readonly status: number;
  readonly statusText: string;
  readonly url: string;
  readonly method: string;
  readonly body: string;
  readonly data: unknown;

  constructor(args: {
    status: number;
    statusText: string;
    url: string;
    method: string;
    body: string;
    data: unknown;
  }) {
    const detail =
      typeof args.data === "object" &&
      args.data !== null &&
      "error" in (args.data as Record<string, unknown>)
        ? String((args.data as Record<string, unknown>).error)
        : args.body.slice(0, 200);
    super(
      `OABP API ${args.method} ${args.url} failed: ${args.status} ${args.statusText}` +
        (detail ? ` — ${detail}` : ""),
    );
    this.name = "OabpApiError";
    this.status = args.status;
    this.statusText = args.statusText;
    this.url = args.url;
    this.method = args.method;
    this.body = args.body;
    this.data = args.data;
  }
}

/** Thrown when the request fails at the network/transport layer. */
export class OabpNetworkError extends OabpError {
  readonly cause: unknown;
  constructor(message: string, cause: unknown) {
    super(message);
    this.name = "OabpNetworkError";
    this.cause = cause;
  }
}

/** Thrown when the request is aborted (timeout or caller-provided signal). */
export class OabpTimeoutError extends OabpError {
  readonly timeoutMs: number;
  constructor(timeoutMs: number) {
    super(`OABP request timed out after ${timeoutMs}ms`);
    this.name = "OabpTimeoutError";
    this.timeoutMs = timeoutMs;
  }
}

/** Thrown when arguments fail client-side validation before any request. */
export class OabpValidationError extends OabpError {
  constructor(message: string) {
    super(message);
    this.name = "OabpValidationError";
  }
}
