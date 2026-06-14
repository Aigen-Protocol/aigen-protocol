/// A tiny, dependency-light mock HTTP layer for exercising the SDK with no
/// network. It builds a `package:http` [MockClient] that records every request
/// and dispatches to handlers keyed by `METHOD /path` (the query string is
/// ignored when matching, but captured for assertions).
///
/// This mirrors the TypeScript SDK's `MockServer` so the same behaviours are
/// asserted across the SDK family.
library;

import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

/// A request as observed by the mock.
class RecordedCall {
  final String method;
  final String url;
  final String path;
  final Map<String, String> query;
  final Object? body;
  final Map<String, String> headers;

  RecordedCall({
    required this.method,
    required this.url,
    required this.path,
    required this.query,
    required this.body,
    required this.headers,
  });
}

/// What a route handler returns.
class MockResponseSpec {
  final int status;
  final Object? json;
  final String? text;
  final Map<String, String> headers;

  const MockResponseSpec({
    this.status = 200,
    this.json,
    this.text,
    this.headers = const {},
  });
}

typedef RouteHandler = MockResponseSpec Function(RecordedCall call);

class MockServer {
  final List<RecordedCall> calls = [];
  final Map<String, RouteHandler> _routes = {};

  /// Register a handler for `METHOD /path` (query ignored when matching).
  MockServer on(String method, String path, RouteHandler handler) {
    _routes['${method.toUpperCase()} $path'] = handler;
    return this;
  }

  /// Convenience: always respond with static [json] for a route.
  MockServer json(String method, String path, Object? json,
          [int status = 200]) =>
      on(method, path, (_) => MockResponseSpec(json: json, status: status));

  /// The `package:http` client to hand to the SDK.
  http.Client get client => MockClient((request) async {
        final uri = request.url;
        final method = request.method.toUpperCase();
        // Dart's Uri.path is already percent-decoded; fall back to decoding the
        // raw path so routing keys (registered with literal characters) match
        // regardless of how the client encoded them.
        final decodedPath = Uri.decodeComponent(uri.path);
        final path = decodedPath.isEmpty ? '/' : decodedPath;

        Object? body;
        if (request.body.isNotEmpty) {
          try {
            body = jsonDecode(request.body);
          } catch (_) {
            body = request.body;
          }
        }

        // HTTP header names are case-insensitive; normalize to lower-case so
        // assertions don't depend on the casing the SDK happened to send.
        final headers = <String, String>{
          for (final e in request.headers.entries) e.key.toLowerCase(): e.value,
        };

        final call = RecordedCall(
          method: method,
          url: uri.toString(),
          path: path,
          query: Map<String, String>.from(uri.queryParameters),
          body: body,
          headers: headers,
        );
        calls.add(call);

        final handler = _routes['$method $path'];
        if (handler == null) {
          return http.Response(
            jsonEncode({'error': 'no mock route for $method $path'}),
            404,
            headers: {'content-type': 'application/json'},
          );
        }
        final spec = handler(call);
        final payload =
            spec.text ?? (spec.json != null ? jsonEncode(spec.json) : '');
        return http.Response(
          payload,
          spec.status,
          headers: {
            'content-type': 'application/json',
            ...spec.headers,
          },
        );
      });

  int countCalls(String method, String path) => calls
      .where((c) => c.method == method.toUpperCase() && c.path == path)
      .length;

  RecordedCall? get lastCall => calls.isEmpty ? null : calls.last;
}
