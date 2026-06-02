import 'package:oabp/oabp.dart';
import 'package:test/test.dart';

import 'mock_server.dart';

const base = 'https://oabp.test';

Map<String, dynamic> sampleMission({Map<String, dynamic> over = const {}}) {
  final now = DateTime.now().millisecondsSinceEpoch ~/ 1000;
  return {
    'id': 'm1',
    'title': 'Ship a Go CLI',
    'description': 'Public repo with a working Go CLI',
    'reward': {'amount': 1000, 'currency': 'AIGEN'},
    'verification_type': 'oracle',
    'verification_params': {
      'oracle_description': 'GitHub repo deliverable owner/name in Go'
    },
    'deadline': now + 3600,
    'status': 'open',
    'submissions': <dynamic>[],
    'creator_agent_id': 'agent://creator',
    ...over,
  };
}

void main() {
  group('OabpClient construction', () {
    test('defaults to the public base URL', () {
      final c = OabpClient();
      expect(c.baseUrl, 'https://cryptogenesis.duckdns.org');
      c.close();
    });

    test('honors a custom base URL and trims the trailing slash', () {
      final c = OabpClient(baseUrl: 'https://example.com/');
      expect(c.baseUrl, 'https://example.com');
      c.close();
    });
  });

  group('listMissions', () {
    late MockServer server;
    late OabpClient client;

    setUp(() {
      server = MockServer();
      client = OabpClient(baseUrl: base, httpClient: server.client);
    });

    test('GETs /api/missions and normalizes the array', () async {
      server.json('GET', '/api/missions', [
        sampleMission(over: {'id': 'a'}),
        sampleMission(over: {
          'id': 'b',
          'reward': {'amount': 5, 'currency': 'USDC'}
        }),
      ]);

      final missions = await client.listMissions();
      expect(missions, hasLength(2));
      expect(missions[0].id, 'a');
      expect(missions[1].reward.currency, RewardCurrency.usdc);
      expect(server.countCalls('GET', '/api/missions'), 1);
    });

    test('passes status as a query param and applies client-side filters',
        () async {
      final now = DateTime.now().millisecondsSinceEpoch ~/ 1000;
      server.json('GET', '/api/missions', [
        sampleMission(
            over: {'id': 'open-oracle', 'verification_type': 'oracle'}),
        sampleMission(over: {
          'id': 'open-regex',
          'verification_type': 'first_valid_match'
        }),
        sampleMission(over: {
          'id': 'expired',
          'verification_type': 'oracle',
          'deadline': now - 10
        }),
        sampleMission(over: {
          'id': 'usdc',
          'verification_type': 'oracle',
          'reward': {'amount': 1, 'currency': 'USDC'}
        }),
      ]);

      final missions = await client.listMissions(const ListMissionsOptions(
        status: MissionStatus.open,
        verificationType: VerificationType.oracle,
        currency: RewardCurrency.aigen,
        excludeExpired: true,
      ));

      expect(missions.map((m) => m.id), ['open-oracle']);
      expect(server.lastCall!.query['status'], 'open');
    });

    test('tolerates a {missions:[...]} envelope shape', () async {
      server.json('GET', '/api/missions', {
        'missions': [
          sampleMission(over: {'id': 'x'})
        ]
      });
      final missions = await client.listMissions();
      expect(missions.map((m) => m.id), ['x']);
    });
  });

  group('getMission', () {
    late MockServer server;
    late OabpClient client;

    setUp(() {
      server = MockServer();
      client = OabpClient(baseUrl: base, httpClient: server.client);
    });

    test('GETs /api/missions/{id} and url-encodes the id', () async {
      server.on(
          'GET',
          '/api/missions/m space',
          (_) =>
              MockResponseSpec(json: sampleMission(over: {'id': 'm space'})));
      final m = await client.getMission('m space');
      expect(m.id, 'm space');
      // The transport must have percent-encoded the space in the request URL.
      expect(server.lastCall!.url, contains('m%20space'));
    });

    test('throws OabpValidationError on an empty id without making a request',
        () async {
      expect(() => client.getMission(''), throwsA(isA<OabpValidationError>()));
      expect(server.calls, isEmpty);
    });

    test('surfaces a 404 as OabpApiError with status and parsed data',
        () async {
      server.json(
          'GET', '/api/missions/nope', {'error': 'mission not found'}, 404);
      final err = await client
          .getMission('nope')
          .then<Object?>((_) => null, onError: (Object e) => e);
      expect(err, isA<OabpApiError>());
      final api = err as OabpApiError;
      expect(api.status, 404);
      expect(api.data, {'error': 'mission not found'});
    });
  });

  group('createMission', () {
    late MockServer server;
    late OabpClient client;

    setUp(() {
      server = MockServer();
      client = OabpClient(baseUrl: base, httpClient: server.client);
    });

    final validReq = CreateMissionRequest.oracle(
      creatorAgentId: 'agent://me',
      title: 'Audit a token',
      description: 'Run a safety review',
      rewardAmount: 250,
      rewardCurrency: RewardCurrency.aigen,
      oracleDescription: 'GoPlus safety review of 0xabc on ethereum',
      deadlineHours: 48,
    );

    test('POSTs the body to /api/missions and returns the created mission',
        () async {
      server.on('POST', '/api/missions', (call) {
        final body = call.body as Map<String, dynamic>;
        return MockResponseSpec(
          status: 201,
          json: sampleMission(over: {'id': 'created', 'title': body['title']}),
        );
      });

      final m = await client.createMission(validReq);
      expect(m.id, 'created');

      final sent = server.lastCall!;
      expect(sent.method, 'POST');
      final body = sent.body as Map<String, dynamic>;
      expect(body['creator_agent_id'], 'agent://me');
      expect(body['reward_amount'], 250);
      expect(body['verification_type'], 'oracle');
      expect(sent.headers['content-type'], contains('application/json'));
    });

    test('validates client-side and never hits the network on bad input',
        () async {
      final negAmount = CreateMissionRequest.oracle(
        creatorAgentId: 'agent://me',
        title: 'x',
        description: 'y',
        rewardAmount: -1,
        rewardCurrency: RewardCurrency.aigen,
        oracleDescription: 'd',
        deadlineHours: 48,
      );
      final zeroDeadline = CreateMissionRequest.oracle(
        creatorAgentId: 'agent://me',
        title: 'x',
        description: 'y',
        rewardAmount: 10,
        rewardCurrency: RewardCurrency.aigen,
        oracleDescription: 'd',
        deadlineHours: 0,
      );

      expect(
          () => client.createMission(negAmount),
          throwsA(isA<OabpValidationError>()
              .having((e) => e.message, 'message', contains('reward_amount'))));
      expect(
          () => client.createMission(zeroDeadline),
          throwsA(isA<OabpValidationError>().having(
              (e) => e.message, 'message', contains('deadline_hours'))));
      expect(server.calls, isEmpty);
    });

    test('requires a compilable regex for first_valid_match missions', () {
      CreateMissionRequest fvm(Map<String, dynamic> vp) => CreateMissionRequest(
            creatorAgentId: 'agent://me',
            title: 'x',
            description: 'y',
            rewardAmount: 10,
            rewardCurrency: RewardCurrency.aigen,
            verificationType: VerificationType.firstValidMatch,
            verificationParams: vp,
            deadlineHours: 24,
          );

      expect(
          () => validateCreateMission(fvm(const {})),
          throwsA(isA<OabpValidationError>().having((e) => e.message, 'message',
              contains('verification_params.regex'))));
      expect(
          () => validateCreateMission(fvm(const {'regex': '([unclosed'})),
          throwsA(isA<OabpValidationError>().having((e) => e.message, 'message',
              contains('not a valid regular expression'))));
      expect(
          () => validateCreateMission(
              fvm(const {'regex': r'^0x[a-fA-F0-9]{40}$'})),
          returnsNormally);
    });
  });

  group('submit', () {
    late MockServer server;
    late OabpClient client;

    setUp(() {
      server = MockServer();
      client = OabpClient(baseUrl: base, httpClient: server.client);
    });

    test('POSTs to /missions/{id}/submit with proof and returns the result',
        () async {
      server.on('POST', '/missions/m1/submit', (call) {
        final body = call.body as Map<String, dynamic>;
        return MockResponseSpec(json: {
          'accepted': true,
          'resolved': true,
          'submission': {
            'submitter_agent_id': body['submitter_agent_id'],
            'proof': body['proof'],
            'verified': true,
          },
        });
      });

      final res = await client.submit(
        'm1',
        const SubmitRequest(
          submitterAgentId: 'agent://me',
          proof: 'https://github.com/owner/repo',
        ),
      );

      expect(res.accepted, true);
      expect(res.resolved, true);
      expect(res.submission?.verified, true);
      final body = server.lastCall!.body as Map<String, dynamic>;
      expect(body['proof'], 'https://github.com/owner/repo');
    });

    test('rejects empty proof / agent id before the request', () async {
      expect(
          () => client.submit(
              'm1', const SubmitRequest(submitterAgentId: '', proof: 'x')),
          throwsA(isA<OabpValidationError>()));
      expect(
          () => client.submit(
              'm1', const SubmitRequest(submitterAgentId: 'a', proof: '  ')),
          throwsA(isA<OabpValidationError>()));
      expect(server.calls, isEmpty);
    });
  });

  group('getStats', () {
    test('GETs /api/stats and fills defaults', () async {
      final server = MockServer();
      final client = OabpClient(baseUrl: base, httpClient: server.client);
      server.json('GET', '/api/stats',
          {'resolved': 12, 'open': 3, 'lifetime_reward_aigen_paid': 108000});
      final stats = await client.getStats();
      expect(stats.resolved, 12);
      expect(stats.open, 3);
      expect(stats.lifetimeRewardAigenPaid, 108000);
    });

    test('coerces a partial / stringy stats payload', () async {
      final server = MockServer();
      final client = OabpClient(baseUrl: base, httpClient: server.client);
      server.json('GET', '/api/stats', {'resolved': '7'});
      final stats = await client.getStats();
      expect(stats.resolved, 7);
      expect(stats.open, 0);
      expect(stats.lifetimeRewardAigenPaid, 0);
    });
  });

  group('reputation', () {
    test('computeReputation aggregates created/won/submitted and net earnings',
        () {
      final missions = [
        Mission.fromJson(sampleMission(over: {
          'id': 'won-aigen',
          'creator_agent_id': 'agent://other',
          'reward': {'amount': 1000, 'currency': 'AIGEN'},
          'status': 'resolved',
          'submissions': [
            {'submitter_agent_id': 'agent://me', 'proof': 'p'}
          ],
          'resolution': {
            'winner_agent_id': 'agent://me',
            'reward_paid': 995,
            'reward_currency': 'AIGEN'
          },
        })),
        Mission.fromJson(sampleMission(over: {
          'id': 'won-usdc',
          'creator_agent_id': 'agent://me',
          'reward': {'amount': 50, 'currency': 'USDC'},
          'status': 'resolved',
          'submissions': [
            {'submitter_agent_id': 'agent://me', 'proof': 'q'}
          ],
          'resolution': {
            'winner_agent_id': 'agent://me',
            'reward_currency': 'USDC'
          },
        })),
        Mission.fromJson(sampleMission(over: {
          'id': 'lost',
          'creator_agent_id': 'agent://other',
          'status': 'resolved',
          'submissions': [
            {'submitter_agent_id': 'agent://me', 'proof': 'r'}
          ],
          'resolution': {
            'winner_agent_id': 'agent://rival',
            'reward_paid': 10,
            'reward_currency': 'AIGEN'
          },
        })),
      ];

      final rep = computeReputation('agent://me', missions);
      expect(rep.missionsCreated, 1);
      expect(rep.missionsWon, 2);
      expect(rep.submissionsMade, 3);
      expect(rep.aigenEarned, 995);
      // USDC win fell back to the mission reward (50) since reward_paid absent.
      expect(rep.usdcEarned, 50);
    });

    test('getReputation merges open + resolved lists and dedupes', () async {
      final server = MockServer();
      final client = OabpClient(baseUrl: base, httpClient: server.client);

      server.on('GET', '/api/missions', (call) {
        if (call.query['status'] == 'resolved') {
          return MockResponseSpec(json: [
            sampleMission(over: {
              'id': 'r1',
              'status': 'resolved',
              'resolution': {
                'winner_agent_id': 'agent://me',
                'reward_paid': 200,
                'reward_currency': 'AIGEN'
              },
            })
          ]);
        }
        return MockResponseSpec(json: [
          sampleMission(over: {'id': 'o1', 'creator_agent_id': 'agent://me'})
        ]);
      });

      final rep = await client.getReputation('agent://me');
      expect(rep.missionsCreated, 1);
      expect(rep.missionsWon, 1);
      expect(rep.aigenEarned, 200);
      expect(server.countCalls('GET', '/api/missions'), 2);
    });
  });

  group('A2A JSON-RPC', () {
    late MockServer server;
    late OabpClient client;

    setUp(() {
      server = MockServer();
      client = OabpClient(baseUrl: base, httpClient: server.client);
    });

    test('message/send wraps params in a JSON-RPC envelope and unwraps result',
        () async {
      server.on('POST', '/api/a2a', (call) {
        final req = call.body as Map<String, dynamic>;
        expect(req['jsonrpc'], '2.0');
        expect(req['method'], 'message/send');
        expect((req['params'] as Map)['message'], isNotNull);
        return MockResponseSpec(json: {
          'jsonrpc': '2.0',
          'id': req['id'],
          'result': {
            'id': 'task-1',
            'status': {'state': 'completed'}
          },
        });
      });

      final res = await client.a2a.sendText('hello agent');
      expect(res.isTask, true);
      expect(res.asTask().id, 'task-1');
      expect(res.asTask().state, 'completed');
    });

    test('tasks/get and tasks/list call the right methods', () async {
      server.on('POST', '/api/a2a', (call) {
        final req = call.body as Map<String, dynamic>;
        final method = req['method'];
        if (method == 'tasks/get') {
          return MockResponseSpec(json: {
            'jsonrpc': '2.0',
            'id': req['id'],
            'result': {'id': (req['params'] as Map)['id']},
          });
        }
        if (method == 'tasks/list') {
          return MockResponseSpec(json: {
            'jsonrpc': '2.0',
            'id': req['id'],
            'result': [
              {'id': 't1'},
              {'id': 't2'}
            ],
          });
        }
        return MockResponseSpec(json: {
          'jsonrpc': '2.0',
          'id': req['id'],
          'error': {'code': -32601, 'message': 'method not found'},
        });
      });

      final task = await client.a2a.getTask('abc');
      expect(task.id, 'abc');
      final tasks = await client.a2a.listTasks();
      expect(tasks.map((t) => t.id), ['t1', 't2']);
    });

    test('maps a JSON-RPC error member to A2aRpcError', () async {
      server.on('POST', '/api/a2a', (call) {
        final req = call.body as Map<String, dynamic>;
        return MockResponseSpec(json: {
          'jsonrpc': '2.0',
          'id': req['id'],
          'error': {
            'code': -32602,
            'message': 'invalid params',
            'data': {'field': 'message'}
          },
        });
      });

      final err = await client.a2a
          .getTask('x')
          .then<Object?>((_) => null, onError: (Object e) => e);
      expect(err, isA<A2aRpcError>());
      final rpc = err as A2aRpcError;
      expect(rpc.code, -32602);
      expect(rpc.data, {'field': 'message'});
    });

    test('fetches the agent card and JWKS from well-known paths', () async {
      server.json('GET', '/.well-known/agent-card.json', {
        'name': 'OABP Agent',
        'version': '1.0.0',
        'signatures': [
          {'protected': 'eyJ...', 'signature': 'abc'}
        ],
      });
      server.json('GET', '/.well-known/jwks.json', {
        'keys': [
          {'kty': 'EC', 'crv': 'P-256', 'kid': 'k1'}
        ]
      });

      final card = await client.a2a.getAgentCard();
      expect(card.name, 'OABP Agent');
      expect(card.isSigned, true);
      final jwks = await client.a2a.getJwks();
      expect(jwks.keys.first.kid, 'k1');
    });
  });

  group('auth + headers + timeout', () {
    test('adds an Authorization bearer header when apiKey is set', () async {
      final server = MockServer();
      final client = OabpClient(
          baseUrl: base, httpClient: server.client, apiKey: 'secret-token');
      server.json('GET', '/api/stats',
          {'resolved': 0, 'open': 0, 'lifetime_reward_aigen_paid': 0});
      await client.getStats();
      expect(server.lastCall!.headers['authorization'], 'Bearer secret-token');
    });

    test('surfaces a server 500 as OabpApiError', () async {
      final server = MockServer();
      final client = OabpClient(baseUrl: base, httpClient: server.client);
      server.json('GET', '/api/stats', {'error': 'boom'}, 500);
      expect(client.getStats(), throwsA(isA<OabpApiError>()));
    });
  });

  group('pure helpers', () {
    test('netReward applies the 0.5% protocol fee', () {
      expect(netReward(1000), 995);
      expect(netReward(50), 49.75);
    });

    test('VerificationType.all lists exactly the four protocol types', () {
      expect(VerificationType.all.map((v) => v.wire).toList()..sort(),
          ['creator_judges', 'first_valid_match', 'oracle', 'peer_vote']);
    });

    test('Mission.listFromJson coerces malformed rows defensively', () {
      final out = Mission.listFromJson([
        {
          'id': 7,
          'reward': {'amount': '12.5', 'currency': 'USDC'}
        },
        null,
        'garbage',
        {'id': 'ok'},
      ]);
      expect(out, hasLength(2));
      expect(out[0].id, '7');
      expect(out[0].reward,
          const Reward(amount: 12.5, currency: RewardCurrency.usdc));
      expect(out[0].submissions, isEmpty);
      expect(out[1].reward.currency, RewardCurrency.aigen);
    });

    test('Reward round-trips through strict json_serializable codec', () {
      const r = Reward(amount: 42, currency: RewardCurrency.usdc);
      final json = r.toJson();
      expect(json, {'amount': 42, 'currency': 'USDC'});
      expect(Reward.fromJsonStrict(json), r);
    });

    test('Mission.toJson preserves unknown server fields (extra)', () {
      final m = Mission.fromJson(sampleMission(over: {'x_custom': 'kept'}));
      expect(m.extra['x_custom'], 'kept');
      expect(m.toJson()['x_custom'], 'kept');
    });
  });
}
