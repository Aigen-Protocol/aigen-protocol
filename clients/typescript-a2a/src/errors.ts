/** Error hierarchy for the OABP / AIGEN SDK. */

/** Base class for every error this SDK throws. */
export class OabpError extends Error {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message);
    this.name = 'OabpError';
    // Preserve `cause` even on runtimes whose Error ctor ignores it.
    if (options && 'cause' in options) {
      (this as { cause?: unknown }).cause = options.cause;
    }
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/** A non-2xx HTTP response from the OABP REST API. */
export class OabpHttpError extends OabpError {
  readonly status: number;
  readonly statusText: string;
  readonly url: string;
  readonly body: string;

  constructor(args: {
    status: number;
    statusText: string;
    url: string;
    body: string;
  }) {
    super(
      `OABP HTTP ${args.status} ${args.statusText} for ${args.url}` +
        (args.body ? `: ${truncate(args.body, 300)}` : ''),
    );
    this.name = 'OabpHttpError';
    this.status = args.status;
    this.statusText = args.statusText;
    this.url = args.url;
    this.body = args.body;
  }
}

/** A JSON-RPC 2.0 error object returned by the A2A endpoint. */
export class A2ARpcError extends OabpError {
  readonly code: number;
  readonly data: unknown;

  constructor(args: { code: number; message: string; data?: unknown }) {
    super(`A2A RPC error ${args.code}: ${args.message}`);
    this.name = 'A2ARpcError';
    this.code = args.code;
    this.data = args.data;
  }
}

/** Agent-card signature verification failed (no usable/valid signature). */
export class AgentCardVerificationError extends OabpError {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = 'AgentCardVerificationError';
  }
}

function truncate(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n)}…` : s;
}
