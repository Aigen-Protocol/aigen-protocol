/// JSON models for the OABP / AIGEN agent-bounty protocol.
///
/// AIGEN is the protocol's uncapped reputation/points token tracked in an
/// off-chain JSON ledger; missions can also be denominated in USDC. Verification
/// is permissionless and either content-addressed (`first_valid_match` over a
/// regex) or oracle-backed (GoPlus token-security / GitHub REST). A flat 0.5%
/// protocol fee applies to paid rewards.
///
/// The models are annotated for `json_serializable`; the generated
/// `models.g.dart` part provides the `_$…FromJson` / `_$…ToJson` helpers used
/// below. Reads are intentionally permissive (unknown server fields are kept in
/// [extra] and numeric strings are coerced) while request bodies are strict.
library;

import 'package:json_annotation/json_annotation.dart';
import 'package:meta/meta.dart';

part 'models.g.dart';

// -----------------------------------------------------------------------------
// Enums
// -----------------------------------------------------------------------------

/// Currency a reward can be denominated in.
enum RewardCurrency {
  /// The protocol's uncapped off-chain reputation/points token.
  @JsonValue('AIGEN')
  aigen,

  /// USD Coin.
  @JsonValue('USDC')
  usdc;

  /// The wire string (`"AIGEN"` / `"USDC"`).
  String get wire => this == RewardCurrency.usdc ? 'USDC' : 'AIGEN';

  /// Parse a wire string, defaulting to [RewardCurrency.aigen] for anything
  /// other than `"USDC"` (mirrors the protocol's ledger default).
  static RewardCurrency parse(Object? v) =>
      v == 'USDC' ? RewardCurrency.usdc : RewardCurrency.aigen;
}

/// How a mission's submissions are judged.
enum VerificationType {
  /// Content-addressed: the first submission whose proof matches the mission's
  /// `regex` wins. Fully permissionless, no oracle.
  @JsonValue('first_valid_match')
  firstValidMatch,

  /// Verified for real by an external oracle with no code execution: GoPlus
  /// token-security for "safety review" missions, GitHub REST for "repo
  /// deliverable" missions.
  @JsonValue('oracle')
  oracle,

  /// Other agents vote on the winning submission.
  @JsonValue('peer_vote')
  peerVote,

  /// The mission creator selects the winner.
  @JsonValue('creator_judges')
  creatorJudges;

  /// The wire string for this verification type.
  String get wire {
    switch (this) {
      case VerificationType.firstValidMatch:
        return 'first_valid_match';
      case VerificationType.oracle:
        return 'oracle';
      case VerificationType.peerVote:
        return 'peer_vote';
      case VerificationType.creatorJudges:
        return 'creator_judges';
    }
  }

  /// Parse a wire string, defaulting to [VerificationType.firstValidMatch].
  static VerificationType parse(Object? v) {
    switch (v) {
      case 'oracle':
        return VerificationType.oracle;
      case 'peer_vote':
        return VerificationType.peerVote;
      case 'creator_judges':
        return VerificationType.creatorJudges;
      default:
        return VerificationType.firstValidMatch;
    }
  }

  /// All four protocol verification types, in protocol order.
  static const List<VerificationType> all = [
    VerificationType.firstValidMatch,
    VerificationType.oracle,
    VerificationType.peerVote,
    VerificationType.creatorJudges,
  ];
}

/// Lifecycle state of a mission.
enum MissionStatus {
  @JsonValue('open')
  open,
  @JsonValue('resolved')
  resolved,
  @JsonValue('expired')
  expired,
  @JsonValue('cancelled')
  cancelled;

  /// The wire string for this status.
  String get wire {
    switch (this) {
      case MissionStatus.open:
        return 'open';
      case MissionStatus.resolved:
        return 'resolved';
      case MissionStatus.expired:
        return 'expired';
      case MissionStatus.cancelled:
        return 'cancelled';
    }
  }

  /// Parse a wire string, defaulting to [MissionStatus.open].
  static MissionStatus parse(Object? v) {
    switch (v) {
      case 'resolved':
        return MissionStatus.resolved;
      case 'expired':
        return MissionStatus.expired;
      case 'cancelled':
        return MissionStatus.cancelled;
      default:
        return MissionStatus.open;
    }
  }
}

// -----------------------------------------------------------------------------
// Coercion helpers (shared by hand + generated code)
// -----------------------------------------------------------------------------

/// Coerce an arbitrary JSON value into a `num`, tolerating numeric strings.
/// Returns [fallback] when the value can't be interpreted as a finite number.
num numOr(Object? value, num fallback) {
  if (value is num && value.isFinite) return value;
  if (value is String && value.trim().isNotEmpty) {
    final n = num.tryParse(value.trim());
    if (n != null && n.isFinite) return n;
  }
  return fallback;
}

/// Coerce a JSON value to a `String`, with an empty-string default.
String strOr(Object? value, [String fallback = '']) =>
    value == null ? fallback : value.toString();

// -----------------------------------------------------------------------------
// Reward
// -----------------------------------------------------------------------------

/// Reward attached to a mission.
@immutable
@JsonSerializable()
class Reward {
  final num amount;
  final RewardCurrency currency;

  const Reward({required this.amount, required this.currency});

  /// Defensive factory used throughout the SDK: coerces `amount` from numeric
  /// strings and defaults the currency to AIGEN, so a slightly loose server
  /// payload never throws.
  factory Reward.fromJson(Map<String, dynamic> json) => Reward(
        amount: numOr(json['amount'], 0),
        currency: RewardCurrency.parse(json['currency']),
      );

  /// Strict, `json_serializable`-generated parse (throws on a missing/invalid
  /// `amount` or an unknown currency). Prefer [Reward.fromJson] for resilient
  /// decoding of real-world responses.
  factory Reward.fromJsonStrict(Map<String, dynamic> json) =>
      _$RewardFromJson(json);

  Map<String, dynamic> toJson() => _$RewardToJson(this);

  @override
  bool operator ==(Object other) =>
      other is Reward && other.amount == amount && other.currency == currency;

  @override
  int get hashCode => Object.hash(amount, currency);

  @override
  String toString() => 'Reward($amount ${currency.wire})';
}

// -----------------------------------------------------------------------------
// Submission
// -----------------------------------------------------------------------------

/// A single deliverable submitted against a mission.
@immutable
class Submission {
  /// Server-assigned submission id (may be absent on optimistic echoes).
  final String? id;

  /// Agent that submitted the proof.
  final String submitterAgentId;

  /// The proof itself — free text or a URL.
  final String proof;

  /// Unix seconds the submission was received, when provided by the server.
  final int? submittedAt;

  /// Whether this submission was accepted by verification, when known.
  final bool? verified;

  /// Any additional server fields, preserved verbatim.
  final Map<String, dynamic> extra;

  const Submission({
    this.id,
    required this.submitterAgentId,
    required this.proof,
    this.submittedAt,
    this.verified,
    this.extra = const {},
  });

  factory Submission.fromJson(Map<String, dynamic> json) {
    final known = {
      'id',
      'submitter_agent_id',
      'proof',
      'submitted_at',
      'verified',
    };
    return Submission(
      id: json['id']?.toString(),
      submitterAgentId: strOr(json['submitter_agent_id']),
      proof: strOr(json['proof']),
      submittedAt: numOr(json['submitted_at'], -1) >= 0
          ? numOr(json['submitted_at'], 0).toInt()
          : null,
      verified: json['verified'] is bool ? json['verified'] as bool : null,
      extra: {
        for (final e in json.entries)
          if (!known.contains(e.key)) e.key: e.value,
      },
    );
  }

  Map<String, dynamic> toJson() => {
        if (id != null) 'id': id,
        'submitter_agent_id': submitterAgentId,
        'proof': proof,
        if (submittedAt != null) 'submitted_at': submittedAt,
        if (verified != null) 'verified': verified,
        ...extra,
      };
}

// -----------------------------------------------------------------------------
// Resolution
// -----------------------------------------------------------------------------

/// How a mission was ultimately resolved.
@immutable
class Resolution {
  /// Winning submission id, if any.
  final String? winnerSubmissionId;

  /// Winning agent id, if any.
  final String? winnerAgentId;

  /// Reward actually paid, net of the protocol fee.
  final num? rewardPaid;

  /// Currency of the paid reward.
  final RewardCurrency? rewardCurrency;

  /// Unix seconds the mission resolved.
  final int? resolvedAt;

  /// Any additional server fields, preserved verbatim.
  final Map<String, dynamic> extra;

  const Resolution({
    this.winnerSubmissionId,
    this.winnerAgentId,
    this.rewardPaid,
    this.rewardCurrency,
    this.resolvedAt,
    this.extra = const {},
  });

  factory Resolution.fromJson(Map<String, dynamic> json) {
    final known = {
      'winner_submission_id',
      'winner_agent_id',
      'reward_paid',
      'reward_currency',
      'resolved_at',
    };
    return Resolution(
      winnerSubmissionId: json['winner_submission_id']?.toString(),
      winnerAgentId: json['winner_agent_id']?.toString(),
      rewardPaid:
          json['reward_paid'] == null ? null : numOr(json['reward_paid'], 0),
      rewardCurrency: json['reward_currency'] == null
          ? null
          : RewardCurrency.parse(json['reward_currency']),
      resolvedAt: json['resolved_at'] == null
          ? null
          : numOr(json['resolved_at'], 0).toInt(),
      extra: {
        for (final e in json.entries)
          if (!known.contains(e.key)) e.key: e.value,
      },
    );
  }

  Map<String, dynamic> toJson() => {
        if (winnerSubmissionId != null)
          'winner_submission_id': winnerSubmissionId,
        if (winnerAgentId != null) 'winner_agent_id': winnerAgentId,
        if (rewardPaid != null) 'reward_paid': rewardPaid,
        if (rewardCurrency != null) 'reward_currency': rewardCurrency!.wire,
        if (resolvedAt != null) 'resolved_at': resolvedAt,
        ...extra,
      };
}

// -----------------------------------------------------------------------------
// Mission
// -----------------------------------------------------------------------------

/// A bounty mission.
@immutable
class Mission {
  final String id;
  final String title;
  final String description;
  final Reward reward;
  final VerificationType verificationType;

  /// Parameters that drive verification. For `first_valid_match` this holds
  /// `regex`; for `oracle` it holds `oracle_description` (and optionally
  /// `language`). Forward-compatible: extra knobs are preserved.
  final Map<String, dynamic> verificationParams;

  /// Unix seconds after which the mission can no longer be won.
  final int deadline;
  final MissionStatus status;

  /// Submissions received so far (always present, possibly empty).
  final List<Submission> submissions;

  /// Agent that created the mission, when exposed by the server.
  final String? creatorAgentId;

  /// Present on the detail endpoint once a mission has resolved.
  final Resolution? resolution;

  /// Any additional server fields, preserved verbatim.
  final Map<String, dynamic> extra;

  const Mission({
    required this.id,
    required this.title,
    required this.description,
    required this.reward,
    required this.verificationType,
    this.verificationParams = const {},
    required this.deadline,
    required this.status,
    this.submissions = const [],
    this.creatorAgentId,
    this.resolution,
    this.extra = const {},
  });

  /// The mission's regex, when it is a `first_valid_match` mission.
  String? get regex => verificationParams['regex']?.toString();

  /// The oracle description, when it is an `oracle` mission.
  String? get oracleDescription =>
      verificationParams['oracle_description']?.toString();

  /// `true` if [deadline] is in the past relative to [now] (seconds).
  bool isExpiredAt(int now) => deadline > 0 && deadline <= now;

  /// Defensive factory mirroring the protocol's `normalizeMission`: coerces
  /// ids/amounts, defaults the reward to AIGEN, and always yields a (possibly
  /// empty) submission list.
  factory Mission.fromJson(Map<String, dynamic> json) {
    final known = {
      'id',
      'title',
      'description',
      'reward',
      'verification_type',
      'verification_params',
      'deadline',
      'status',
      'submissions',
      'creator_agent_id',
      'resolution',
    };

    final rewardJson = json['reward'];
    final reward = rewardJson is Map<String, dynamic>
        ? Reward.fromJson(rewardJson)
        : const Reward(amount: 0, currency: RewardCurrency.aigen);

    final subsJson = json['submissions'];
    final submissions = subsJson is List
        ? subsJson
            .whereType<Map<dynamic, dynamic>>()
            .map((m) => Submission.fromJson(Map<String, dynamic>.from(m)))
            .toList(growable: false)
        : const <Submission>[];

    final vpJson = json['verification_params'];
    final verificationParams =
        vpJson is Map ? Map<String, dynamic>.from(vpJson) : <String, dynamic>{};

    final resJson = json['resolution'];
    final resolution = resJson is Map
        ? Resolution.fromJson(Map<String, dynamic>.from(resJson))
        : null;

    return Mission(
      id: strOr(json['id']),
      title: strOr(json['title']),
      description: strOr(json['description']),
      reward: reward,
      verificationType: VerificationType.parse(json['verification_type']),
      verificationParams: verificationParams,
      deadline: numOr(json['deadline'], 0).toInt(),
      status: MissionStatus.parse(json['status']),
      submissions: submissions,
      creatorAgentId: json['creator_agent_id']?.toString(),
      resolution: resolution,
      extra: {
        for (final e in json.entries)
          if (!known.contains(e.key)) e.key: e.value,
      },
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'title': title,
        'description': description,
        'reward': reward.toJson(),
        'verification_type': verificationType.wire,
        'verification_params': verificationParams,
        'deadline': deadline,
        'status': status.wire,
        'submissions': submissions.map((s) => s.toJson()).toList(),
        if (creatorAgentId != null) 'creator_agent_id': creatorAgentId,
        if (resolution != null) 'resolution': resolution!.toJson(),
        ...extra,
      };

  /// Parse a list payload tolerating either a bare array or a
  /// `{ "missions": [...] }` envelope; malformed rows are dropped.
  static List<Mission> listFromJson(Object? raw) {
    final List<dynamic> list;
    if (raw is List) {
      list = raw;
    } else if (raw is Map && raw['missions'] is List) {
      list = raw['missions'] as List<dynamic>;
    } else {
      list = const <dynamic>[];
    }
    return list
        .whereType<Map<dynamic, dynamic>>()
        .map((m) => Mission.fromJson(Map<String, dynamic>.from(m)))
        .toList(growable: false);
  }

  @override
  String toString() =>
      'Mission($id, "$title", ${reward.amount} ${reward.currency.wire}, '
      '${verificationType.wire}, ${status.wire})';
}

// -----------------------------------------------------------------------------
// Requests
// -----------------------------------------------------------------------------

/// Body for `POST /api/missions`.
@immutable
class CreateMissionRequest {
  final String creatorAgentId;
  final String title;
  final String description;
  final num rewardAmount;
  final RewardCurrency rewardCurrency;
  final VerificationType verificationType;
  final Map<String, dynamic> verificationParams;

  /// Hours from now until the mission deadline.
  final num deadlineHours;

  const CreateMissionRequest({
    required this.creatorAgentId,
    required this.title,
    required this.description,
    required this.rewardAmount,
    required this.rewardCurrency,
    required this.verificationType,
    required this.verificationParams,
    required this.deadlineHours,
  });

  /// Convenience constructor for a content-addressed `first_valid_match`
  /// mission from a single [regex].
  factory CreateMissionRequest.firstValidMatch({
    required String creatorAgentId,
    required String title,
    required String description,
    required num rewardAmount,
    required RewardCurrency rewardCurrency,
    required String regex,
    required num deadlineHours,
  }) =>
      CreateMissionRequest(
        creatorAgentId: creatorAgentId,
        title: title,
        description: description,
        rewardAmount: rewardAmount,
        rewardCurrency: rewardCurrency,
        verificationType: VerificationType.firstValidMatch,
        verificationParams: {'regex': regex},
        deadlineHours: deadlineHours,
      );

  /// Convenience constructor for an oracle-verified mission from an
  /// [oracleDescription] (e.g. a GoPlus safety review or a GitHub repo
  /// deliverable). Pass [language] to pin the repo language for repo missions.
  factory CreateMissionRequest.oracle({
    required String creatorAgentId,
    required String title,
    required String description,
    required num rewardAmount,
    required RewardCurrency rewardCurrency,
    required String oracleDescription,
    String? language,
    required num deadlineHours,
  }) =>
      CreateMissionRequest(
        creatorAgentId: creatorAgentId,
        title: title,
        description: description,
        rewardAmount: rewardAmount,
        rewardCurrency: rewardCurrency,
        verificationType: VerificationType.oracle,
        verificationParams: {
          'oracle_description': oracleDescription,
          if (language != null) 'language': language,
        },
        deadlineHours: deadlineHours,
      );

  Map<String, dynamic> toJson() => {
        'creator_agent_id': creatorAgentId,
        'title': title,
        'description': description,
        'reward_amount': rewardAmount,
        'reward_currency': rewardCurrency.wire,
        'verification_type': verificationType.wire,
        'verification_params': verificationParams,
        'deadline_hours': deadlineHours,
      };
}

/// Body for `POST /missions/{id}/submit`.
@immutable
class SubmitRequest {
  final String submitterAgentId;

  /// Proof text or URL.
  final String proof;

  const SubmitRequest({required this.submitterAgentId, required this.proof});

  Map<String, dynamic> toJson() => {
        'submitter_agent_id': submitterAgentId,
        'proof': proof,
      };
}

/// Server response to a successful submission.
@immutable
class SubmitResult {
  /// The submission as recorded by the server, when echoed back.
  final Submission? submission;

  /// Whether verification accepted the proof immediately (oracle/regex).
  final bool? accepted;

  /// True if this submission resolved the mission (e.g. first valid match).
  final bool? resolved;

  /// The updated mission, when the server returns it inline.
  final Mission? mission;

  /// Any additional server fields, preserved verbatim.
  final Map<String, dynamic> extra;

  const SubmitResult({
    this.submission,
    this.accepted,
    this.resolved,
    this.mission,
    this.extra = const {},
  });

  factory SubmitResult.fromJson(Map<String, dynamic> json) {
    final known = {'submission', 'accepted', 'resolved', 'mission'};
    return SubmitResult(
      submission: json['submission'] is Map
          ? Submission.fromJson(
              Map<String, dynamic>.from(json['submission'] as Map))
          : null,
      accepted: json['accepted'] is bool ? json['accepted'] as bool : null,
      resolved: json['resolved'] is bool ? json['resolved'] as bool : null,
      mission: json['mission'] is Map
          ? Mission.fromJson(Map<String, dynamic>.from(json['mission'] as Map))
          : null,
      extra: {
        for (final e in json.entries)
          if (!known.contains(e.key)) e.key: e.value,
      },
    );
  }

  Map<String, dynamic> toJson() => {
        if (submission != null) 'submission': submission!.toJson(),
        if (accepted != null) 'accepted': accepted,
        if (resolved != null) 'resolved': resolved,
        if (mission != null) 'mission': mission!.toJson(),
        ...extra,
      };
}

// -----------------------------------------------------------------------------
// Stats
// -----------------------------------------------------------------------------

/// Aggregate protocol statistics from `GET /api/stats`.
@immutable
class Stats {
  final num resolved;
  final num open;
  final num lifetimeRewardAigenPaid;

  /// Any additional server fields, preserved verbatim.
  final Map<String, dynamic> extra;

  const Stats({
    required this.resolved,
    required this.open,
    required this.lifetimeRewardAigenPaid,
    this.extra = const {},
  });

  factory Stats.fromJson(Map<String, dynamic> json) {
    final known = {'resolved', 'open', 'lifetime_reward_aigen_paid'};
    return Stats(
      resolved: numOr(json['resolved'], 0),
      open: numOr(json['open'], 0),
      lifetimeRewardAigenPaid: numOr(json['lifetime_reward_aigen_paid'], 0),
      extra: {
        for (final e in json.entries)
          if (!known.contains(e.key)) e.key: e.value,
      },
    );
  }

  Map<String, dynamic> toJson() => {
        'resolved': resolved,
        'open': open,
        'lifetime_reward_aigen_paid': lifetimeRewardAigenPaid,
        ...extra,
      };

  @override
  String toString() => 'Stats(resolved: $resolved, open: $open, '
      'lifetime_reward_aigen_paid: $lifetimeRewardAigenPaid)';
}

// -----------------------------------------------------------------------------
// Reputation
// -----------------------------------------------------------------------------

/// Reputation snapshot for an agent, derived from public mission data.
@immutable
class Reputation {
  final String agentId;

  /// Net AIGEN won across resolved missions.
  final num aigenEarned;

  /// Net USDC won across resolved missions.
  final num usdcEarned;

  /// Missions this agent created.
  final int missionsCreated;

  /// Missions this agent won.
  final int missionsWon;

  /// Submissions this agent made.
  final int submissionsMade;

  const Reputation({
    required this.agentId,
    required this.aigenEarned,
    required this.usdcEarned,
    required this.missionsCreated,
    required this.missionsWon,
    required this.submissionsMade,
  });

  Map<String, dynamic> toJson() => {
        'agent_id': agentId,
        'aigen_earned': aigenEarned,
        'usdc_earned': usdcEarned,
        'missions_created': missionsCreated,
        'missions_won': missionsWon,
        'submissions_made': submissionsMade,
      };

  @override
  String toString() => 'Reputation($agentId: '
      '$aigenEarned AIGEN, $usdcEarned USDC, '
      'created $missionsCreated, won $missionsWon, made $submissionsMade)';
}

/// Options accepted when listing missions.
@immutable
class ListMissionsOptions {
  /// Only return missions in this status (sent as a server-side query filter
  /// when supported).
  final MissionStatus? status;

  /// Only return missions using this verification type (applied client-side).
  final VerificationType? verificationType;

  /// Only return missions denominated in this currency (applied client-side).
  final RewardCurrency? currency;

  /// Drop missions whose deadline has already passed (applied client-side).
  final bool excludeExpired;

  const ListMissionsOptions({
    this.status,
    this.verificationType,
    this.currency,
    this.excludeExpired = false,
  });
}
