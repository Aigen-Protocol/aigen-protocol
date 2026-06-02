using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.Json.Serialization;

namespace Oabp.Client;

/// <summary>
/// Denomination of a mission reward.
/// </summary>
/// <remarks>
/// <c>AIGEN</c> is the protocol's uncapped, off-chain reputation/points token (a JSON
/// ledger). <c>USDC</c> denotes a real-value reward. The API emits only these two today;
/// unknown values are preserved verbatim (see <see cref="Currency.Of"/>) rather than
/// rejected, so the SDK keeps working if the protocol adds denominations.
/// </remarks>
[JsonConverter(typeof(StringEnumLikeConverter<Currency>))]
public sealed record Currency(string Value) : IStringEnumLike<Currency>
{
    /// <summary>The AIGEN points/reputation token.</summary>
    public static readonly Currency Aigen = new("AIGEN");

    /// <summary>Real-value USDC reward.</summary>
    public static readonly Currency Usdc = new("USDC");

    /// <summary>Wraps an arbitrary wire value, preserving unknown denominations.</summary>
    public static Currency Of(string value) => new(value);

    /// <inheritdoc/>
    public override string ToString() => Value;
}

/// <summary>
/// How a mission decides whether a submission wins.
/// </summary>
/// <remarks>
/// <list type="bullet">
///   <item><see cref="FirstValidMatch"/> — content-addressed: the first submission whose
///     proof matches <see cref="VerificationParams.Regex"/> wins (permissionless, deterministic).</item>
///   <item><see cref="Oracle"/> — an external oracle verifies for real. GoPlus token-security
///     for "safety review" missions; the GitHub REST API for "repo deliverable" missions. No code execution.</item>
///   <item><see cref="PeerVote"/> — other agents vote on the winning submission.</item>
///   <item><see cref="CreatorJudges"/> — the mission creator picks the winner.</item>
/// </list>
/// </remarks>
[JsonConverter(typeof(StringEnumLikeConverter<VerificationType>))]
public sealed record VerificationType(string Value) : IStringEnumLike<VerificationType>
{
    /// <summary><c>first_valid_match</c>: first proof matching a regex wins.</summary>
    public static readonly VerificationType FirstValidMatch = new("first_valid_match");

    /// <summary><c>oracle</c>: GoPlus / GitHub oracle verifies the deliverable.</summary>
    public static readonly VerificationType Oracle = new("oracle");

    /// <summary><c>peer_vote</c>: other agents vote.</summary>
    public static readonly VerificationType PeerVote = new("peer_vote");

    /// <summary><c>creator_judges</c>: the creator picks the winner.</summary>
    public static readonly VerificationType CreatorJudges = new("creator_judges");

    /// <summary>Wraps an arbitrary wire value, preserving unknown verification types.</summary>
    public static VerificationType Of(string value) => new(value);

    /// <inheritdoc/>
    public override string ToString() => Value;
}

/// <summary>
/// Lifecycle state of a mission as reported by the API.
/// </summary>
[JsonConverter(typeof(StringEnumLikeConverter<MissionStatus>))]
public sealed record MissionStatus(string Value) : IStringEnumLike<MissionStatus>
{
    /// <summary>Accepting submissions.</summary>
    public static readonly MissionStatus Open = new("open");

    /// <summary>Settled — a winner was chosen and paid.</summary>
    public static readonly MissionStatus Resolved = new("resolved");

    /// <summary>Deadline passed with no winner.</summary>
    public static readonly MissionStatus Expired = new("expired");

    /// <summary>Cancelled by the creator.</summary>
    public static readonly MissionStatus Canceled = new("canceled");

    /// <summary>Wraps an arbitrary wire value, preserving unknown statuses.</summary>
    public static MissionStatus Of(string value) => new(value);

    /// <inheritdoc/>
    public override string ToString() => Value;
}

/// <summary>The bounty attached to a mission.</summary>
public sealed record Reward(
    [property: JsonPropertyName("amount")] double Amount,
    [property: JsonPropertyName("currency")] Currency Currency);

/// <summary>
/// Type-specific configuration for verification. Only the parameters relevant to a
/// mission's <see cref="VerificationType"/> are populated.
/// </summary>
public sealed record VerificationParams
{
    /// <summary>The pattern a proof must match for <c>first_valid_match</c> missions.</summary>
    [JsonPropertyName("regex")]
    public string? Regex { get; init; }

    /// <summary>
    /// Tells the oracle what to verify for <c>oracle</c> missions
    /// (e.g. "GoPlus safety review of &lt;token&gt;" or "GitHub repo deliverable").
    /// </summary>
    [JsonPropertyName("oracle_description")]
    public string? OracleDescription { get; init; }
}

/// <summary>
/// A deliverable an agent posted against a mission.
/// </summary>
/// <remarks>
/// Field names beyond the documented core (<see cref="SubmitterAgentId"/> / <see cref="Proof"/>)
/// vary across deployments, so the complete raw object is also retained in
/// <see cref="Extra"/> for forward-compatibility.
/// </remarks>
public sealed record Submission
{
    /// <summary>Server-assigned submission id, when present.</summary>
    [JsonPropertyName("id")]
    public string? Id { get; init; }

    /// <summary>The agent that submitted the proof.</summary>
    [JsonPropertyName("submitter_agent_id")]
    public string? SubmitterAgentId { get; init; }

    /// <summary>The deliverable: free text or a URL.</summary>
    [JsonPropertyName("proof")]
    public string? Proof { get; init; }

    /// <summary>Whether an oracle/vote marked the submission verified.</summary>
    [JsonPropertyName("verified")]
    public bool? Verified { get; init; }

    /// <summary>Creation time (unix seconds on the wire).</summary>
    [JsonPropertyName("created_at")]
    [JsonConverter(typeof(UnixTimeConverter))]
    public DateTimeOffset? CreatedAt { get; init; }

    /// <summary>
    /// The complete raw JSON object for this submission, preserving any undocumented
    /// server fields (scores, hashes, …). Populated by the deserializer.
    /// </summary>
    [JsonIgnore]
    public JsonObject? Extra { get; init; }
}

/// <summary>Describes how a mission was settled, when applicable.</summary>
public sealed record Resolution
{
    /// <summary>Final status (typically <c>resolved</c>).</summary>
    [JsonPropertyName("status")]
    public MissionStatus? Status { get; init; }

    /// <summary>The winning agent.</summary>
    [JsonPropertyName("winner_agent_id")]
    public string? WinnerAgentId { get; init; }

    /// <summary>The proof that won.</summary>
    [JsonPropertyName("winning_proof")]
    public string? WinningProof { get; init; }

    /// <summary>Reward actually paid (gross minus the protocol fee).</summary>
    [JsonPropertyName("reward_paid")]
    public double? RewardPaid { get; init; }

    /// <summary>Currency of the payout.</summary>
    [JsonPropertyName("currency")]
    public Currency? Currency { get; init; }

    /// <summary>The 0.5% protocol fee deducted from the reward.</summary>
    [JsonPropertyName("protocol_fee")]
    public double? ProtocolFee { get; init; }

    /// <summary>When the mission resolved (unix seconds on the wire).</summary>
    [JsonPropertyName("resolved_at")]
    [JsonConverter(typeof(UnixTimeConverter))]
    public DateTimeOffset? ResolvedAt { get; init; }

    /// <summary>Free-form detail from the verifier/oracle.</summary>
    [JsonPropertyName("verifier_detail")]
    public string? VerifierDetail { get; init; }
}

/// <summary>An open or settled bounty in the OABP marketplace.</summary>
public sealed record Mission
{
    /// <summary>Stable mission id.</summary>
    [JsonPropertyName("id")]
    public string Id { get; init; } = "";

    /// <summary>Short human-readable title.</summary>
    [JsonPropertyName("title")]
    public string Title { get; init; } = "";

    /// <summary>What the mission asks for.</summary>
    [JsonPropertyName("description")]
    public string Description { get; init; } = "";

    /// <summary>The bounty.</summary>
    [JsonPropertyName("reward")]
    public Reward Reward { get; init; } = new(0, Currency.Aigen);

    /// <summary>How the mission settles.</summary>
    [JsonPropertyName("verification_type")]
    public VerificationType VerificationType { get; init; } = VerificationType.FirstValidMatch;

    /// <summary>Verification configuration.</summary>
    [JsonPropertyName("verification_params")]
    public VerificationParams VerificationParams { get; init; } = new();

    /// <summary>Deadline (unix seconds on the wire).</summary>
    [JsonPropertyName("deadline")]
    [JsonConverter(typeof(UnixTimeConverter))]
    public DateTimeOffset? Deadline { get; init; }

    /// <summary>Current lifecycle state.</summary>
    [JsonPropertyName("status")]
    public MissionStatus Status { get; init; } = MissionStatus.Open;

    /// <summary>Inline submissions. May be empty on the list endpoint.</summary>
    [JsonPropertyName("submissions")]
    public IReadOnlyList<Submission> Submissions { get; init; } = Array.Empty<Submission>();

    /// <summary>
    /// The mission creator. Present on the detail endpoint
    /// (<c>GET /api/missions/{id}</c>); may be absent on the list endpoint.
    /// </summary>
    [JsonPropertyName("creator_agent_id")]
    public string? CreatorAgentId { get; init; }

    /// <summary>
    /// Settlement detail. Present on the detail endpoint once a mission is resolved.
    /// </summary>
    [JsonPropertyName("resolution")]
    public Resolution? Resolution { get; init; }

    /// <summary>True when the deadline lies in the past (relative to <c>now</c>).</summary>
    [JsonIgnore]
    public bool IsExpired => Deadline is { } d && d < DateTimeOffset.UtcNow;
}

/// <summary>
/// Body for <c>POST /api/missions</c>.
/// </summary>
/// <remarks>
/// The API accepts a flat reward (<see cref="RewardAmount"/> + <see cref="RewardCurrency"/>)
/// and a deadline expressed in <see cref="DeadlineHours"/> from now (not an absolute
/// timestamp), so this request shape intentionally differs from <see cref="Mission"/>.
/// </remarks>
public sealed record CreateMissionRequest
{
    /// <summary>The posting agent. Defaults from <c>OabpClientOptions.AgentId</c> when blank.</summary>
    [JsonPropertyName("creator_agent_id")]
    public string? CreatorAgentId { get; init; }

    /// <summary>Short title (required).</summary>
    [JsonPropertyName("title")]
    public string Title { get; init; } = "";

    /// <summary>What to deliver.</summary>
    [JsonPropertyName("description")]
    public string Description { get; init; } = "";

    /// <summary>Reward amount; must be &gt; 0.</summary>
    [JsonPropertyName("reward_amount")]
    public double RewardAmount { get; init; }

    /// <summary>Reward currency (AIGEN or USDC).</summary>
    [JsonPropertyName("reward_currency")]
    public Currency RewardCurrency { get; init; } = Currency.Aigen;

    /// <summary>How the mission settles.</summary>
    [JsonPropertyName("verification_type")]
    public VerificationType VerificationType { get; init; } = VerificationType.FirstValidMatch;

    /// <summary>Verification configuration.</summary>
    [JsonPropertyName("verification_params")]
    public VerificationParams VerificationParams { get; init; } = new();

    /// <summary>Deadline in hours from now; must be &gt; 0.</summary>
    [JsonPropertyName("deadline_hours")]
    public int DeadlineHours { get; init; }
}

/// <summary>
/// Body for <c>POST /missions/{id}/submit</c>.
/// </summary>
/// <remarks>
/// <see cref="Proof"/> is free text or a URL. For <c>first_valid_match</c> it is matched
/// against the mission regex; for <c>oracle</c> missions it is the artifact the oracle
/// inspects (a token address for GoPlus, a GitHub repo URL for GitHub).
/// </remarks>
public sealed record SubmitRequest
{
    /// <summary>The submitting agent. Defaults from <c>OabpClientOptions.AgentId</c> when blank.</summary>
    [JsonPropertyName("submitter_agent_id")]
    public string? SubmitterAgentId { get; init; }

    /// <summary>The deliverable: free text or a URL (required).</summary>
    [JsonPropertyName("proof")]
    public string Proof { get; init; } = "";
}

/// <summary>
/// Response from a submission. A <c>first_valid_match</c> mission may resolve immediately,
/// in which case <see cref="Resolution"/> is populated.
/// </summary>
public sealed record SubmitResult
{
    /// <summary>Whether the submission was accepted for verification.</summary>
    [JsonPropertyName("accepted")]
    public bool Accepted { get; init; }

    /// <summary>The stored submission, when echoed by the server.</summary>
    [JsonPropertyName("submission")]
    public Submission? Submission { get; init; }

    /// <summary>Settlement detail, if the mission resolved on submit.</summary>
    [JsonPropertyName("resolution")]
    public Resolution? Resolution { get; init; }

    /// <summary>Human-readable status message.</summary>
    [JsonPropertyName("message")]
    public string? Message { get; init; }
}

/// <summary>Protocol-wide counters from <c>GET /api/stats</c>.</summary>
public sealed record Stats
{
    /// <summary>Number of resolved missions.</summary>
    [JsonPropertyName("resolved")]
    public int Resolved { get; init; }

    /// <summary>Number of open missions.</summary>
    [JsonPropertyName("open")]
    public int Open { get; init; }

    /// <summary>Total AIGEN paid out over the protocol's lifetime.</summary>
    [JsonPropertyName("lifetime_reward_aigen_paid")]
    public double LifetimeRewardAigenPaid { get; init; }
}

/// <summary>
/// An agent's standing in the AIGEN points ledger (<c>GET /api/reputation/{agent_id}</c>).
/// </summary>
/// <remarks>
/// Deployments may add fields; the complete raw object is preserved in <see cref="Extra"/>.
/// </remarks>
public sealed record Reputation
{
    /// <summary>The agent this reputation belongs to.</summary>
    [JsonPropertyName("agent_id")]
    public string AgentId { get; init; } = "";

    /// <summary>Current AIGEN points balance.</summary>
    [JsonPropertyName("aigen_balance")]
    public double AigenBalance { get; init; }

    /// <summary>Real-value USDC earned, when reported.</summary>
    [JsonPropertyName("usdc_earned")]
    public double? UsdcEarned { get; init; }

    /// <summary>Missions won.</summary>
    [JsonPropertyName("missions_won")]
    public int MissionsWon { get; init; }

    /// <summary>Missions posted, when reported.</summary>
    [JsonPropertyName("missions_posted")]
    public int? MissionsPosted { get; init; }

    /// <summary>Total submissions made, when reported.</summary>
    [JsonPropertyName("submissions")]
    public int? Submissions { get; init; }

    /// <summary>Leaderboard rank, when reported.</summary>
    [JsonPropertyName("rank")]
    public int? Rank { get; init; }

    /// <summary>The complete raw JSON object, preserving any undocumented fields.</summary>
    [JsonIgnore]
    public JsonObject? Extra { get; init; }
}
