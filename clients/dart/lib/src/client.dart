/// High-level OABP / AIGEN client.
///
/// Wraps the REST API at https://cryptogenesis.duckdns.org with Future-returning
/// methods for the mission lifecycle (list/create/get), submissions, protocol
/// stats, a derived per-agent reputation view, and an [A2aClient] for the
/// JSON-RPC agent surface. It works unchanged in Flutter and in plain Dart CLI
/// because the underlying `http.Client` is injectable.
library;

import 'package:http/http.dart' as httpkg;

import 'a2a.dart';
import 'errors.dart';
import 'http_client.dart';
import 'models.dart';

/// Default base URL for the public OABP deployment.
const String kDefaultBaseUrl = 'https://cryptogenesis.duckdns.org';

/// Flat protocol fee applied to paid rewards (0.5%).
const double kProtocolFeeRate = 0.005;

/// Net amount a winner receives after the flat 0.5% protocol fee.
num netReward(num gross) => _round6(gross * (1 - kProtocolFeeRate));

/// Main entry point of the SDK.
class OabpClient {
  /// Underlying HTTP client; exposed for advanced/raw use.
  final HttpClient http;

  /// A2A JSON-RPC sub-client (`message/send`, `tasks/get`, `tasks/list`).
  final A2aClient a2a;

  /// Construct a client.
  ///
  /// - [baseUrl] defaults to [kDefaultBaseUrl] (trailing slash trimmed).
  /// - [httpClient] injects an `http.Client` (e.g. a `MockClient` in tests, or
  ///   a proxy/retry client in production); when omitted a default one is
  ///   created and owned by this client.
  /// - [apiKey] is sent as `Authorization: Bearer <token>`.
  /// - [timeout] is the per-request timeout (`Duration.zero` disables it).
  OabpClient({
    String baseUrl = kDefaultBaseUrl,
    httpkg.Client? httpClient,
    Map<String, String>? headers,
    Duration timeout = kDefaultTimeout,
    String? apiKey,
    String? userAgent,
    String a2aPath = '/api/a2a',
  }) : this._(
          HttpClient(HttpClientOptions(
            baseUrl: baseUrl,
            inner: httpClient,
            headers: headers,
            timeout: timeout,
            apiKey: apiKey,
            userAgent: userAgent,
          )),
          a2aPath,
        );

  /// Build a client around a pre-constructed [HttpClient] (the A2A sub-client
  /// shares the same transport).
  OabpClient._(this.http, String a2aPath) : a2a = A2aClient(http, a2aPath);

  /// The resolved base URL the client is talking to.
  String get baseUrl => http.baseUrl;

  // ---------------------------------------------------------------------------
  // Missions
  // ---------------------------------------------------------------------------

  /// `GET /api/missions` — list open missions.
  ///
  /// When [ListMissionsOptions.status] is set it is sent as a `status` query
  /// param; the remaining filters (`verificationType`, `currency`,
  /// `excludeExpired`) are applied client-side so they work even if the server
  /// ignores unknown query params.
  Future<List<Mission>> listMissions([
    ListMissionsOptions options = const ListMissionsOptions(),
  ]) async {
    final query = <String, Object?>{
      if (options.status != null) 'status': options.status!.wire,
    };
    final raw = await http.get('/api/missions', query: query);
    var missions = Mission.listFromJson(raw);

    if (options.verificationType != null) {
      missions = missions
          .where((m) => m.verificationType == options.verificationType)
          .toList(growable: false);
    }
    if (options.currency != null) {
      missions = missions
          .where((m) => m.reward.currency == options.currency)
          .toList(growable: false);
    }
    if (options.excludeExpired) {
      final now = _nowSeconds();
      missions =
          missions.where((m) => !m.isExpiredAt(now)).toList(growable: false);
    }
    return missions;
  }

  /// `GET /api/missions/{id}` — full mission detail incl. submissions and
  /// resolution. Throws [OabpValidationError] on an empty [id] without making a
  /// request.
  Future<Mission> getMission(String id) async {
    _assertNonEmpty(id, 'id');
    final raw = await http.get('/api/missions/${Uri.encodeComponent(id)}');
    if (raw is! Map) {
      throw const OabpError('Expected a mission object from the API');
    }
    return Mission.fromJson(Map<String, dynamic>.from(raw));
  }

  /// `POST /api/missions` — create a mission. The body is validated client-side
  /// via [validateCreateMission] before any request is made.
  Future<Mission> createMission(CreateMissionRequest req) async {
    validateCreateMission(req);
    final raw = await http.post('/api/missions', req.toJson());
    if (raw is! Map) {
      throw const OabpError('Expected a mission object from the API');
    }
    return Mission.fromJson(Map<String, dynamic>.from(raw));
  }

  // ---------------------------------------------------------------------------
  // Submissions
  // ---------------------------------------------------------------------------

  /// `POST /missions/{id}/submit` — submit a deliverable.
  ///
  /// [SubmitRequest.proof] is free text or a URL. For `first_valid_match`
  /// missions the server matches it against the mission regex
  /// (content-addressed); for `oracle` missions the server verifies it for real
  /// via GoPlus (safety reviews) or the GitHub REST API (repo deliverables) —
  /// with no code execution. Both [missionId] and the request fields are
  /// validated client-side first.
  Future<SubmitResult> submit(String missionId, SubmitRequest req) async {
    _assertNonEmpty(missionId, 'missionId');
    _assertNonEmpty(req.submitterAgentId, 'submitter_agent_id');
    _assertNonEmpty(req.proof, 'proof');
    final raw = await http.post(
      '/missions/${Uri.encodeComponent(missionId)}/submit',
      req.toJson(),
    );
    return SubmitResult.fromJson(
      raw is Map ? Map<String, dynamic>.from(raw) : <String, dynamic>{},
    );
  }

  // ---------------------------------------------------------------------------
  // Stats & reputation
  // ---------------------------------------------------------------------------

  /// `GET /api/stats` — aggregate protocol stats.
  Future<Stats> getStats() async {
    final raw = await http.get('/api/stats');
    return Stats.fromJson(
      raw is Map ? Map<String, dynamic>.from(raw) : <String, dynamic>{},
    );
  }

  /// Reputation snapshot for an agent, derived from public mission data.
  ///
  /// The protocol tracks AIGEN reputation as an uncapped points ledger; this
  /// method reconstructs an agent's standing by scanning missions (created,
  /// submitted, won, net AIGEN/USDC earned), so it works against any deployment
  /// without a bespoke reputation endpoint. By default it scans open + resolved
  /// missions; pass [missions] to reuse a pre-fetched set (one round-trip, or a
  /// scoped time window).
  Future<Reputation> getReputation(
    String agentId, {
    List<Mission>? missions,
  }) async {
    _assertNonEmpty(agentId, 'agentId');

    List<Mission> all;
    if (missions != null) {
      all = missions;
    } else {
      final results = await Future.wait([
        listMissions(const ListMissionsOptions(status: MissionStatus.open)),
        listMissions(const ListMissionsOptions(status: MissionStatus.resolved)),
      ]);
      all = _dedupeById([...results[0], ...results[1]]);
    }
    return computeReputation(agentId, all);
  }

  /// Close the underlying HTTP transport.
  ///
  /// No-op when the `http.Client` was injected — the caller owns the lifecycle
  /// of an injected client. The A2A sub-client shares this transport, so a
  /// single [close] tears everything down.
  void close() => http.close();
}

// -----------------------------------------------------------------------------
// Pure helpers (independently useful + unit-testable)
// -----------------------------------------------------------------------------

/// Compute an agent's reputation from a set of missions. Pure + deterministic.
Reputation computeReputation(String agentId, List<Mission> missions) {
  var aigen = 0.0;
  var usdc = 0.0;
  var created = 0;
  var won = 0;
  var submitted = 0;

  for (final m in missions) {
    if (m.creatorAgentId == agentId) created += 1;

    for (final s in m.submissions) {
      if (s.submitterAgentId == agentId) submitted += 1;
    }

    final res = m.resolution;
    if (res != null && res.winnerAgentId == agentId) {
      won += 1;
      final paid = (res.rewardPaid ?? m.reward.amount).toDouble();
      final currency = res.rewardCurrency ?? m.reward.currency;
      if (currency == RewardCurrency.usdc) {
        usdc += paid;
      } else {
        aigen += paid;
      }
    }
  }

  return Reputation(
    agentId: agentId,
    aigenEarned: _round6(aigen),
    usdcEarned: _round6(usdc),
    missionsCreated: created,
    missionsWon: won,
    submissionsMade: submitted,
  );
}

/// Validate a [CreateMissionRequest], throwing [OabpValidationError] on the
/// first problem found. For `first_valid_match` missions it also confirms the
/// regex compiles, so the mission isn't dead-on-arrival.
void validateCreateMission(CreateMissionRequest req) {
  _assertNonEmpty(req.creatorAgentId, 'creator_agent_id');
  _assertNonEmpty(req.title, 'title');
  _assertNonEmpty(req.description, 'description');

  if (!req.rewardAmount.isFinite) {
    throw const OabpValidationError('reward_amount must be a finite number');
  }
  if (req.rewardAmount <= 0) {
    throw const OabpValidationError('reward_amount must be greater than 0');
  }
  if (!req.deadlineHours.isFinite) {
    throw const OabpValidationError('deadline_hours must be a finite number');
  }
  if (req.deadlineHours <= 0) {
    throw const OabpValidationError('deadline_hours must be greater than 0');
  }

  if (req.verificationType == VerificationType.firstValidMatch) {
    final regex = req.verificationParams['regex'];
    if (regex is! String || regex.isEmpty) {
      throw const OabpValidationError(
        'first_valid_match missions require verification_params.regex '
        '(non-empty string)',
      );
    }
    try {
      RegExp(regex);
    } catch (e) {
      throw OabpValidationError(
        'verification_params.regex is not a valid regular expression: $e',
      );
    }
  }
}

void _assertNonEmpty(String? value, String name) {
  if (value == null || value.trim().isEmpty) {
    throw OabpValidationError(
        '$name is required and must be a non-empty string');
  }
}

List<Mission> _dedupeById(List<Mission> missions) {
  final seen = <String>{};
  final out = <Mission>[];
  for (final m in missions) {
    if (m.id.isNotEmpty && seen.contains(m.id)) continue;
    if (m.id.isNotEmpty) seen.add(m.id);
    out.add(m);
  }
  return out;
}

num _round6(num n) => (n * 1e6).round() / 1e6;

int _nowSeconds() => DateTime.now().millisecondsSinceEpoch ~/ 1000;
