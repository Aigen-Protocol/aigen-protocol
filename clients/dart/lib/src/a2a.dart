/// A2A (Agent-to-Agent) JSON-RPC 2.0 client for the OABP protocol.
///
/// The protocol exposes an A2A endpoint at `POST /api/a2a` with the methods
/// `message/send`, `tasks/get`, and `tasks/list`, an ES256-signed agent card at
/// `/.well-known/agent-card.json`, and a JWKS at `/.well-known/jwks.json`.
///
/// This client speaks the JSON-RPC envelope, surfaces RPC-level errors as a
/// typed [A2aRpcError], and can fetch the agent card and JWKS so callers can
/// verify the card signature with their own crypto library if desired.
library;

import 'package:meta/meta.dart';

import 'errors.dart';
import 'http_client.dart';

/// A part of an A2A message (text is the common case for OABP).
@immutable
class A2aPart {
  /// `text`, `file` or `data`.
  final String kind;
  final String? text;
  final Map<String, dynamic> extra;

  const A2aPart({required this.kind, this.text, this.extra = const {}});

  /// A single text part.
  const A2aPart.text(String value) : this(kind: 'text', text: value);

  factory A2aPart.fromJson(Map<String, dynamic> json) {
    final known = {'kind', 'text'};
    return A2aPart(
      kind: (json['kind'] ?? 'text').toString(),
      text: json['text']?.toString(),
      extra: {
        for (final e in json.entries)
          if (!known.contains(e.key)) e.key: e.value,
      },
    );
  }

  Map<String, dynamic> toJson() => {
        'kind': kind,
        if (text != null) 'text': text,
        ...extra,
      };
}

/// An A2A message.
@immutable
class A2aMessage {
  /// `user` or `agent`.
  final String role;
  final List<A2aPart> parts;
  final String? messageId;
  final Map<String, dynamic> extra;

  const A2aMessage({
    required this.role,
    required this.parts,
    this.messageId,
    this.extra = const {},
  });

  /// Build a single-text-part `user` message.
  factory A2aMessage.text(String text, {String? messageId}) => A2aMessage(
        role: 'user',
        parts: [A2aPart.text(text)],
        messageId: messageId,
      );

  /// Concatenate the text of every text part (handy for reading replies).
  String get textContent =>
      parts.where((p) => p.text != null).map((p) => p.text!).join();

  factory A2aMessage.fromJson(Map<String, dynamic> json) {
    final known = {'role', 'parts', 'messageId'};
    final partsJson = json['parts'];
    return A2aMessage(
      role: (json['role'] ?? 'agent').toString(),
      parts: partsJson is List
          ? partsJson
              .whereType<Map<dynamic, dynamic>>()
              .map((p) => A2aPart.fromJson(Map<String, dynamic>.from(p)))
              .toList(growable: false)
          : const <A2aPart>[],
      messageId: json['messageId']?.toString(),
      extra: {
        for (final e in json.entries)
          if (!known.contains(e.key)) e.key: e.value,
      },
    );
  }

  Map<String, dynamic> toJson() => {
        'role': role,
        'parts': parts.map((p) => p.toJson()).toList(),
        if (messageId != null) 'messageId': messageId,
        ...extra,
      };
}

/// An A2A task as returned by `tasks/get` / `tasks/list`.
@immutable
class A2aTask {
  final String id;

  /// Status object, commonly `{ "state": "completed" }`.
  final Map<String, dynamic>? status;
  final List<A2aMessage> history;
  final List<dynamic> artifacts;
  final Map<String, dynamic> extra;

  const A2aTask({
    required this.id,
    this.status,
    this.history = const [],
    this.artifacts = const [],
    this.extra = const {},
  });

  /// The task state string (`status['state']`), when present.
  String? get state => status?['state']?.toString();

  factory A2aTask.fromJson(Map<String, dynamic> json) {
    final known = {'id', 'status', 'history', 'artifacts'};
    final historyJson = json['history'];
    return A2aTask(
      id: (json['id'] ?? '').toString(),
      status: json['status'] is Map
          ? Map<String, dynamic>.from(json['status'] as Map)
          : null,
      history: historyJson is List
          ? historyJson
              .whereType<Map<dynamic, dynamic>>()
              .map((m) => A2aMessage.fromJson(Map<String, dynamic>.from(m)))
              .toList(growable: false)
          : const <A2aMessage>[],
      artifacts: json['artifacts'] is List
          ? List<dynamic>.from(json['artifacts'] as List)
          : const [],
      extra: {
        for (final e in json.entries)
          if (!known.contains(e.key)) e.key: e.value,
      },
    );
  }
}

/// Result of `message/send`: either a direct [A2aMessage] reply or a created
/// [A2aTask]. Use [isTask] / [asTask] / [asMessage] to discriminate.
@immutable
class SendMessageResult {
  /// The raw decoded JSON result.
  final Map<String, dynamic> raw;

  const SendMessageResult(this.raw);

  /// `true` when the result looks like a task (has an `id` and no `role`).
  bool get isTask => raw.containsKey('id') && !raw.containsKey('role');

  /// Interpret the result as an [A2aTask].
  A2aTask asTask() => A2aTask.fromJson(raw);

  /// Interpret the result as an [A2aMessage].
  A2aMessage asMessage() => A2aMessage.fromJson(raw);
}

/// A single public signing key from the JWKS document.
@immutable
class Jwk {
  final Map<String, dynamic> raw;
  const Jwk(this.raw);

  String? get kty => raw['kty']?.toString();
  String? get crv => raw['crv']?.toString();
  String? get kid => raw['kid']?.toString();
  String? get alg => raw['alg']?.toString();
}

/// JWKS document at `/.well-known/jwks.json`.
@immutable
class Jwks {
  final List<Jwk> keys;
  const Jwks(this.keys);

  factory Jwks.fromJson(Map<String, dynamic> json) {
    final keysJson = json['keys'];
    return Jwks(keysJson is List
        ? keysJson
            .whereType<Map<dynamic, dynamic>>()
            .map((k) => Jwk(Map<String, dynamic>.from(k)))
            .toList(growable: false)
        : const <Jwk>[]);
  }
}

/// The agent card served at `/.well-known/agent-card.json`.
@immutable
class AgentCard {
  final Map<String, dynamic> raw;
  const AgentCard(this.raw);

  String get name => (raw['name'] ?? '').toString();
  String? get description => raw['description']?.toString();
  String? get url => raw['url']?.toString();
  String? get version => raw['version']?.toString();

  /// Detached JWS signatures over the card, when the server signs it.
  List<dynamic> get signatures =>
      raw['signatures'] is List ? raw['signatures'] as List : const [];

  /// `true` when the card carries at least one detached signature.
  bool get isSigned => signatures.isNotEmpty;

  factory AgentCard.fromJson(Map<String, dynamic> json) => AgentCard(json);
}

/// A2A JSON-RPC client bound to an [HttpClient].
class A2aClient {
  final HttpClient _http;
  final String rpcPath;
  int _rpcCounter = 0;

  A2aClient(this._http, [this.rpcPath = '/api/a2a']);

  String _nextRpcId() {
    _rpcCounter += 1;
    final stamp = DateTime.now().microsecondsSinceEpoch.toRadixString(36);
    return 'oabp-$stamp-$_rpcCounter';
  }

  /// Low-level JSON-RPC call. Throws [A2aRpcError] when the response carries an
  /// `error` member, and the usual [OabpApiError] / network errors otherwise.
  Future<R> call<R>(String method, [Map<String, dynamic>? params]) async {
    final id = _nextRpcId();
    final payload = <String, dynamic>{
      'jsonrpc': '2.0',
      'id': id,
      'method': method,
      if (params != null) 'params': params,
    };

    final decoded = await _http.post(rpcPath, payload);
    if (decoded is! Map) {
      throw const OabpError('A2A response was not a JSON-RPC object');
    }
    final map = Map<String, dynamic>.from(decoded);
    final error = map['error'];
    if (error is Map) {
      throw A2aRpcError(
        code: numOrInt(error['code'], -32603),
        rpcMessage: (error['message'] ?? 'unknown error').toString(),
        data: error['data'],
      );
    }
    return map['result'] as R;
  }

  /// `message/send` — send a message; returns a [SendMessageResult] that may be
  /// a direct reply or a created task.
  Future<SendMessageResult> sendMessage(
    A2aMessage message, {
    Map<String, dynamic>? configuration,
  }) async {
    final params = <String, dynamic>{
      'message': message.toJson(),
      if (configuration != null) 'configuration': configuration,
    };
    final result = await call<Object?>('message/send', params);
    return SendMessageResult(
      result is Map ? Map<String, dynamic>.from(result) : <String, dynamic>{},
    );
  }

  /// Convenience: send a plain-text message in one call.
  Future<SendMessageResult> sendText(String text) =>
      sendMessage(A2aMessage.text(text));

  /// `tasks/get` — fetch a task by id.
  Future<A2aTask> getTask(String id) async {
    final result = await call<Object?>('tasks/get', {'id': id});
    return A2aTask.fromJson(
      result is Map ? Map<String, dynamic>.from(result) : <String, dynamic>{},
    );
  }

  /// `tasks/list` — list tasks (optionally filtered by server-supported keys).
  Future<List<A2aTask>> listTasks([Map<String, dynamic>? params]) async {
    final result = await call<Object?>('tasks/list', params ?? const {});
    if (result is! List) return const [];
    return result
        .whereType<Map<dynamic, dynamic>>()
        .map((m) => A2aTask.fromJson(Map<String, dynamic>.from(m)))
        .toList(growable: false);
  }

  /// Fetch the ES256-signed agent card.
  Future<AgentCard> getAgentCard() async {
    final decoded = await _http.get('/.well-known/agent-card.json');
    return AgentCard.fromJson(
      decoded is Map ? Map<String, dynamic>.from(decoded) : <String, dynamic>{},
    );
  }

  /// Fetch the JWKS used to verify the agent-card signature.
  Future<Jwks> getJwks() async {
    final decoded = await _http.get('/.well-known/jwks.json');
    return Jwks.fromJson(
      decoded is Map ? Map<String, dynamic>.from(decoded) : <String, dynamic>{},
    );
  }
}

/// Coerce a JSON value to an `int` with a fallback (JSON-RPC error codes,
/// timestamps, …).
int numOrInt(Object? value, int fallback) {
  if (value is int) return value;
  if (value is num && value.isFinite) return value.toInt();
  if (value is String) {
    final n = int.tryParse(value.trim());
    if (n != null) return n;
  }
  return fallback;
}
