/// Error types thrown by the OABP SDK.
///
/// Every error extends [OabpError] (which implements [Exception]) and carries
/// structured context so callers can branch on the failure cause with a single
/// `on OabpApiError catch (e)` / `on OabpTimeoutError catch (e)` etc.
library;

/// Base class for every error the SDK throws.
class OabpError implements Exception {
  /// Human-readable description of the failure.
  final String message;

  const OabpError(this.message);

  @override
  String toString() => '$runtimeType: $message';
}

/// Thrown when the API responds with a non-2xx status.
///
/// Exposes the HTTP [status], the raw response [body], and a [data] field that
/// holds the parsed JSON body when the payload was valid JSON (otherwise it is
/// the raw string, or `null` for an empty body).
class OabpApiError extends OabpError {
  /// HTTP status code (e.g. 404, 422, 500).
  final int status;

  /// Reason phrase associated with [status], when the transport provides one.
  final String statusText;

  /// The request URL that produced the error.
  final String url;

  /// The HTTP method of the failing request.
  final String method;

  /// The raw, undecoded response body.
  final String body;

  /// Parsed JSON body when the payload was JSON; the raw string or `null`
  /// otherwise.
  final Object? data;

  OabpApiError({
    required this.status,
    required this.statusText,
    required this.url,
    required this.method,
    required this.body,
    required this.data,
  }) : super(_describe(status, statusText, url, method, body, data));

  static String _describe(
    int status,
    String statusText,
    String url,
    String method,
    String body,
    Object? data,
  ) {
    String detail;
    if (data is Map && data['error'] != null) {
      detail = data['error'].toString();
    } else {
      detail = body.length > 200 ? body.substring(0, 200) : body;
    }
    final suffix = detail.isEmpty ? '' : ' — $detail';
    return 'OABP API $method $url failed: $status $statusText$suffix';
  }
}

/// Thrown when the request fails at the network/transport layer (DNS, refused
/// connection, TLS, socket reset, …) before any HTTP status is received.
class OabpNetworkError extends OabpError {
  /// The underlying error/exception, when one is available.
  final Object? cause;

  const OabpNetworkError(super.message, [this.cause]);
}

/// Thrown when a request exceeds the client's configured timeout.
class OabpTimeoutError extends OabpError {
  /// The timeout, in milliseconds, that was exceeded.
  final int timeoutMs;

  OabpTimeoutError(this.timeoutMs)
      : super('OABP request timed out after ${timeoutMs}ms');
}

/// Thrown when arguments fail client-side validation before any request is
/// made (e.g. an empty id, a non-positive reward, or an invalid regex).
class OabpValidationError extends OabpError {
  const OabpValidationError(super.message);
}

/// Thrown when an A2A JSON-RPC call returns an `error` member.
class A2aRpcError extends OabpError {
  /// JSON-RPC error code (e.g. -32601 method not found, -32602 invalid params).
  final int code;

  /// Optional structured `data` member from the JSON-RPC error object.
  final Object? data;

  A2aRpcError({required this.code, required String rpcMessage, this.data})
      : super('A2A RPC error $code: $rpcMessage');
}
