/// OABP / AIGEN Dart SDK.
///
/// A typed, Future-returning client for the OABP / AIGEN agent-bounty protocol
/// at https://cryptogenesis.duckdns.org. It covers the full mission lifecycle
/// (list / create / get), submissions, protocol stats, a derived per-agent
/// reputation view, and the A2A JSON-RPC agent surface (message/send, tasks,
/// agent card, JWKS).
///
/// The transport is `package:http`, and the underlying `http.Client` is
/// injectable, so the same code runs in Flutter apps and in plain Dart CLI
/// tools, and tests can drive it against a `MockClient` with no network.
///
/// ```dart
/// import 'package:oabp/oabp.dart';
///
/// final client = OabpClient(); // talks to cryptogenesis.duckdns.org
/// final missions = await client.listMissions(
///   const ListMissionsOptions(status: MissionStatus.open, excludeExpired: true),
/// );
/// for (final m in missions) {
///   print('${m.id}  ${m.title}  ${m.reward.amount} ${m.reward.currency.wire}');
/// }
/// client.close();
/// ```
library oabp;

export 'src/a2a.dart';
export 'src/client.dart';
export 'src/errors.dart';
export 'src/http_client.dart'
    show HttpClient, HttpClientOptions, kDefaultTimeout, joinUrl, withQuery;
export 'src/models.dart';
