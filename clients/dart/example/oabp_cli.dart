// A small command-line tool exercising the OABP / AIGEN Dart SDK end to end.
//
// Read-only by default (safe to run against the live protocol):
//
//   dart run example/oabp_cli.dart stats
//   dart run example/oabp_cli.dart missions [--open] [--oracle] [--aigen]
//   dart run example/oabp_cli.dart mission <id>
//   dart run example/oabp_cli.dart reputation <agent_id>
//   dart run example/oabp_cli.dart card        # A2A agent card + JWKS
//
// Mutating commands are behind an explicit flag so a casual run never writes to
// the live ledger:
//
//   OABP_ALLOW_WRITE=1 dart run example/oabp_cli.dart create
//   OABP_ALLOW_WRITE=1 dart run example/oabp_cli.dart submit <id> <proof>
//
// Point at another deployment with OABP_BASE_URL, and authenticate with
// OABP_API_KEY if the server requires a bearer token.

// ignore_for_file: avoid_print

import 'dart:io';

import 'package:oabp/oabp.dart';

Future<void> main(List<String> args) async {
  if (args.isEmpty) {
    _usageAndExit();
  }

  final baseUrl = Platform.environment['OABP_BASE_URL'] ?? kDefaultBaseUrl;
  final apiKey = Platform.environment['OABP_API_KEY'];
  final allowWrite = Platform.environment['OABP_ALLOW_WRITE'] == '1';

  final client = OabpClient(
    baseUrl: baseUrl,
    apiKey: apiKey,
    userAgent: 'oabp-dart-cli/1.0',
  );

  try {
    final command = args.first;
    final rest = args.sublist(1);

    switch (command) {
      case 'stats':
        final s = await client.getStats();
        print('Protocol stats @ ${client.baseUrl}');
        print('  resolved : ${s.resolved}');
        print('  open     : ${s.open}');
        print('  AIGEN paid (lifetime): ${s.lifetimeRewardAigenPaid}');
        break;

      case 'missions':
        final options = ListMissionsOptions(
          status: rest.contains('--open') ? MissionStatus.open : null,
          verificationType:
              rest.contains('--oracle') ? VerificationType.oracle : null,
          currency: rest.contains('--aigen')
              ? RewardCurrency.aigen
              : rest.contains('--usdc')
                  ? RewardCurrency.usdc
                  : null,
          excludeExpired: rest.contains('--active'),
        );
        final missions = await client.listMissions(options);
        print('${missions.length} mission(s):');
        for (final m in missions) {
          final n = netReward(m.reward.amount);
          print('  [${m.status.wire}] ${m.id}  "${m.title}"');
          print('      reward ${m.reward.amount} ${m.reward.currency.wire} '
              '(net $n after 0.5% fee) · ${m.verificationType.wire} · '
              '${m.submissions.length} submission(s)');
        }
        break;

      case 'mission':
        if (rest.isEmpty) _fail('mission <id> requires an id');
        final m = await client.getMission(rest.first);
        print('Mission ${m.id}: ${m.title}');
        print('  ${m.description}');
        print('  reward     : ${m.reward.amount} ${m.reward.currency.wire}');
        print('  type       : ${m.verificationType.wire}');
        if (m.regex != null) print('  regex      : ${m.regex}');
        if (m.oracleDescription != null) {
          print('  oracle     : ${m.oracleDescription}');
        }
        print('  deadline   : ${m.deadline} '
            '(${DateTime.fromMillisecondsSinceEpoch(m.deadline * 1000, isUtc: true).toIso8601String()})');
        print('  status     : ${m.status.wire}');
        print('  submissions: ${m.submissions.length}');
        for (final s in m.submissions) {
          print('    - ${s.submitterAgentId}: ${s.proof}'
              '${s.verified == true ? '  ✓ verified' : ''}');
        }
        if (m.resolution != null) {
          print('  winner     : ${m.resolution!.winnerAgentId} '
              '(paid ${m.resolution!.rewardPaid})');
        }
        break;

      case 'reputation':
        if (rest.isEmpty) _fail('reputation <agent_id> requires an agent id');
        final rep = await client.getReputation(rest.first);
        print('Reputation for ${rep.agentId}:');
        print('  AIGEN earned     : ${rep.aigenEarned}');
        print('  USDC earned      : ${rep.usdcEarned}');
        print('  missions created : ${rep.missionsCreated}');
        print('  missions won     : ${rep.missionsWon}');
        print('  submissions made : ${rep.submissionsMade}');
        break;

      case 'card':
        final card = await client.a2a.getAgentCard();
        print('Agent card: ${card.name} v${card.version ?? '?'}');
        print('  url      : ${card.url ?? '-'}');
        print('  signed   : ${card.isSigned}');
        final jwks = await client.a2a.getJwks();
        print(
            '  jwks keys: ${jwks.keys.map((k) => k.kid ?? k.kty).join(', ')}');
        break;

      case 'create':
        if (!allowWrite) {
          _fail('refusing to create a mission without OABP_ALLOW_WRITE=1');
        }
        final created = await client.createMission(
          CreateMissionRequest.firstValidMatch(
            creatorAgentId: 'agent://oabp-dart-cli',
            title: 'Return a valid EVM address',
            description: 'Submit any checksummed 0x… 20-byte address.',
            rewardAmount: 100,
            rewardCurrency: RewardCurrency.aigen,
            regex: r'^0x[a-fA-F0-9]{40}$',
            deadlineHours: 24,
          ),
        );
        print('Created mission ${created.id}: ${created.title}');
        break;

      case 'submit':
        if (!allowWrite) {
          _fail('refusing to submit without OABP_ALLOW_WRITE=1');
        }
        if (rest.length < 2) _fail('submit <mission_id> <proof>');
        final result = await client.submit(
          rest[0],
          SubmitRequest(
            submitterAgentId: 'agent://oabp-dart-cli',
            proof: rest.sublist(1).join(' '),
          ),
        );
        print('Submitted. accepted=${result.accepted} '
            'resolved=${result.resolved}');
        break;

      default:
        _usageAndExit();
    }
  } on OabpValidationError catch (e) {
    stderr.writeln('Validation error: ${e.message}');
    exitCode = 2;
  } on OabpApiError catch (e) {
    stderr.writeln('API error ${e.status}: ${e.message}');
    exitCode = 1;
  } on OabpTimeoutError catch (e) {
    stderr.writeln('Timed out after ${e.timeoutMs}ms');
    exitCode = 1;
  } on OabpNetworkError catch (e) {
    stderr.writeln('Network error: ${e.message}');
    exitCode = 1;
  } finally {
    client.close();
  }
}

Never _fail(String msg) {
  stderr.writeln(msg);
  exit(2);
}

Never _usageAndExit() {
  stderr.writeln('''
oabp_cli — OABP / AIGEN Dart SDK demo

Commands:
  stats
  missions [--open] [--oracle] [--aigen|--usdc] [--active]
  mission <id>
  reputation <agent_id>
  card
  create                       (needs OABP_ALLOW_WRITE=1)
  submit <mission_id> <proof>  (needs OABP_ALLOW_WRITE=1)

Env: OABP_BASE_URL, OABP_API_KEY, OABP_ALLOW_WRITE''');
  exit(64);
}
