/// Thin, typed HTTP layer over `package:http`.
///
/// Adds JSON encoding/decoding, query-string assembly, a per-request timeout,
/// bearer auth, default headers and structured error mapping. The underlying
/// [http.Client] is injectable, which is what lets the test-suite drive the SDK
/// against a [MockClient] with no real network.
library;

import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'errors.dart';

/// Default per-request timeout (30s). Pass `Duration.zero` to disable.
const Duration kDefaultTimeout = Duration(seconds: 30);

/// Strip a single trailing slash so path joins stay predictable.
String _trimTrailingSlash(String s) =>
    s.endsWith('/') ? s.substring(0, s.length - 1) : s;

/// Join `base` + `path`, tolerating leading/trailing slashes on either side.
String joinUrl(String baseUrl, String path) {
  final base = _trimTrailingSlash(baseUrl);
  final p = path.startsWith('/') ? path : '/$path';
  return '$base$p';
}

/// Append query params to a URL, skipping `null` values.
String withQuery(String url, Map<String, Object?>? query) {
  if (query == null || query.isEmpty) return url;
  final pairs = <String>[];
  query.forEach((k, v) {
    if (v == null) return;
    pairs.add(
        '${Uri.encodeQueryComponent(k)}=${Uri.encodeQueryComponent('$v')}');
  });
  if (pairs.isEmpty) return url;
  final sep = url.contains('?') ? '&' : '?';
  return '$url$sep${pairs.join('&')}';
}

/// Best-effort JSON decode: returns the decoded value, or the raw string when
/// the body is not valid JSON, or `null` for an empty body.
Object? safeJsonDecode(String text) {
  if (text.isEmpty) return null;
  try {
    return jsonDecode(text);
  } catch (_) {
    return text;
  }
}

/// Configuration for an [HttpClient].
class HttpClientOptions {
  final String baseUrl;

  /// Underlying transport. Defaults to a fresh [http.Client]; inject a
  /// [MockClient] in tests or a custom client (proxy, retry, …) in production.
  final http.Client? inner;

  /// Headers sent on every request (merged with, and overridden by, per-request
  /// headers).
  final Map<String, String>? headers;

  /// Per-request timeout. `Duration.zero` disables the SDK-managed timeout.
  final Duration timeout;

  /// Optional bearer token sent as `Authorization: Bearer <token>`.
  final String? apiKey;

  /// Optional `User-Agent` header.
  final String? userAgent;

  const HttpClientOptions({
    required this.baseUrl,
    this.inner,
    this.headers,
    this.timeout = kDefaultTimeout,
    this.apiKey,
    this.userAgent,
  });
}

/// Typed HTTP client returning decoded JSON.
class HttpClient {
  final String baseUrl;
  final http.Client _inner;
  final bool _ownsInner;
  final Map<String, String> _baseHeaders;
  final Duration _timeout;

  HttpClient(HttpClientOptions opts)
      : baseUrl = _trimTrailingSlash(opts.baseUrl),
        _inner = opts.inner ?? http.Client(),
        _ownsInner = opts.inner == null,
        _timeout = opts.timeout,
        _baseHeaders = _buildHeaders(opts);

  static Map<String, String> _buildHeaders(HttpClientOptions opts) {
    final h = <String, String>{
      'Accept': 'application/json',
      if (opts.headers != null) ...opts.headers!,
    };
    if (opts.apiKey != null && opts.apiKey!.isNotEmpty) {
      h['Authorization'] = 'Bearer ${opts.apiKey}';
    }
    if (opts.userAgent != null && opts.userAgent!.isNotEmpty) {
      h['User-Agent'] = opts.userAgent!;
    }
    return h;
  }

  /// Issue a request and return the decoded JSON body.
  ///
  /// Throws [OabpApiError] on a non-2xx response, [OabpTimeoutError] when the
  /// request exceeds the configured timeout, and [OabpNetworkError] on any
  /// transport-level failure.
  Future<Object?> request(
    String method,
    String path, {
    Map<String, Object?>? query,
    Object? body,
    Map<String, String>? headers,
  }) async {
    final url = withQuery(joinUrl(baseUrl, path), query);
    final uri = Uri.parse(url);

    final reqHeaders = <String, String>{
      ..._baseHeaders,
      if (headers != null) ...headers,
    };

    String? encodedBody;
    if (body != null) {
      reqHeaders['Content-Type'] = 'application/json';
      encodedBody = jsonEncode(body);
    }

    final request = http.Request(method, uri)..headers.addAll(reqHeaders);
    if (encodedBody != null) request.body = encodedBody;

    http.StreamedResponse streamed;
    try {
      var send = _inner.send(request);
      if (_timeout > Duration.zero) {
        send = send.timeout(
          _timeout,
          onTimeout: () => throw OabpTimeoutError(_timeout.inMilliseconds),
        );
      }
      streamed = await send;
    } on OabpTimeoutError {
      rethrow;
    } on TimeoutException {
      throw OabpTimeoutError(_timeout.inMilliseconds);
    } catch (err) {
      throw OabpNetworkError(
        'Network request to $url failed: $err',
        err,
      );
    }

    final responseBody = await streamed.stream.bytesToString();
    final data = safeJsonDecode(responseBody);
    final ok = streamed.statusCode >= 200 && streamed.statusCode < 300;

    if (!ok) {
      throw OabpApiError(
        status: streamed.statusCode,
        statusText:
            streamed.reasonPhrase ?? _statusTextFor(streamed.statusCode),
        url: url,
        method: method,
        body: responseBody,
        data: data,
      );
    }
    return data;
  }

  /// `GET path` decoded as JSON.
  Future<Object?> get(String path,
          {Map<String, Object?>? query, Map<String, String>? headers}) =>
      request('GET', path, query: query, headers: headers);

  /// `POST path` with a JSON [body], decoded as JSON.
  Future<Object?> post(String path, Object? body,
          {Map<String, Object?>? query, Map<String, String>? headers}) =>
      request('POST', path, body: body, query: query, headers: headers);

  /// Close the underlying transport. No-op when the client was injected
  /// (the caller owns the lifecycle of an injected [http.Client]).
  void close() {
    if (_ownsInner) _inner.close();
  }

  static String _statusTextFor(int status) {
    const map = {
      200: 'OK',
      201: 'Created',
      204: 'No Content',
      400: 'Bad Request',
      401: 'Unauthorized',
      403: 'Forbidden',
      404: 'Not Found',
      409: 'Conflict',
      422: 'Unprocessable Entity',
      429: 'Too Many Requests',
      500: 'Internal Server Error',
      502: 'Bad Gateway',
      503: 'Service Unavailable',
    };
    return map[status] ?? '';
  }
}
