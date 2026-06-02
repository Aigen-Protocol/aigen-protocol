using System.Net;
using Xunit;

namespace Oabp.Client.Tests;

public sealed class OabpClientTests
{
    private const string BaseUrl = "https://api.test.local";

    private static OabpClient NewClient(HttpMessageHandler handler, string? agentId = null, string? apiKey = null)
    {
        var http = new HttpClient(handler);
        return new OabpClient(http, new OabpClientOptions
        {
            BaseUrl = BaseUrl,
            AgentId = agentId,
            ApiKey = apiKey,
        });
    }

    [Fact]
    public async Task ListMissions_decodes_array_and_unix_deadline()
    {
        var handler = new FakeApiHandler();
        using var client = NewClient(handler);

        IReadOnlyList<Mission> missions = await client.ListMissionsAsync();

        Assert.Equal(2, missions.Count);
        Assert.Equal("m-1", missions[0].Id);
        Assert.Equal(VerificationType.Oracle, missions[0].VerificationType);
        Assert.Equal("GoPlus safety review of 0xabc", missions[0].VerificationParams.OracleDescription);
        Assert.Equal(Currency.Usdc, missions[1].Reward.Currency);
        Assert.Equal(1000, missions[1].Reward.Amount);
        Assert.Equal("^[a-f0-9]{64}$", missions[1].VerificationParams.Regex);
        // Deadline decoded from unix seconds into a real timestamp.
        Assert.NotNull(missions[0].Deadline);
        Assert.Equal(handler.EchoDeadline, missions[0].Deadline!.Value.ToUnixTimeSeconds());
        Assert.Equal("GET", handler.LastMethod);
        Assert.Equal("/api/missions", handler.LastPath);
    }

    [Fact]
    public async Task GetMission_decodes_detail_submissions_resolution_and_extra()
    {
        var handler = new FakeApiHandler();
        using var client = NewClient(handler);

        Mission m = await client.GetMissionAsync("m-1");

        Assert.Equal(MissionStatus.Resolved, m.Status);
        // Unix 1893456000 -> 2030-01-01T00:00:00Z
        Assert.Equal(
            new DateTimeOffset(2030, 1, 1, 0, 0, 0, TimeSpan.Zero),
            m.Deadline!.Value.ToUniversalTime());

        Submission s = Assert.Single(m.Submissions);
        Assert.Equal("agent.alice", s.SubmitterAgentId);
        Assert.True(s.Verified);
        Assert.Equal(1700000000, s.CreatedAt!.Value.ToUnixTimeSeconds());
        // Undocumented "score" field survives in Extra.
        Assert.NotNull(s.Extra);
        Assert.True(s.Extra!.ContainsKey("score"));
        Assert.Equal(0.98, s.Extra["score"]!.GetValue<double>(), 3);

        Assert.NotNull(m.Resolution);
        Assert.Equal("agent.alice", m.Resolution!.WinnerAgentId);
        Assert.Equal(1.25, m.Resolution.ProtocolFee);
        Assert.Equal(248.75, m.Resolution.RewardPaid); // 250 minus the 0.5% fee
    }

    [Fact]
    public async Task GetMission_missing_throws_not_found_with_decoded_message()
    {
        var handler = new FakeApiHandler();
        using var client = NewClient(handler);

        OabpApiException ex = await Assert.ThrowsAsync<OabpApiException>(
            () => client.GetMissionAsync("does-not-exist"));

        Assert.True(ex.IsNotFound);
        Assert.Equal(HttpStatusCode.NotFound, ex.StatusCode);
        Assert.Equal("mission not found", ex.ResponseMessage);
        Assert.Contains("mission not found", ex.Message);
    }

    [Fact]
    public async Task CreateMission_defaults_agent_id_and_sends_exact_fields()
    {
        var handler = new FakeApiHandler();
        using var client = NewClient(handler, agentId: "agent.creator");

        Mission m = await client.CreateMissionAsync(new CreateMissionRequest
        {
            Title = "Repo deliverable: .NET SDK",
            Description = "ship a working SDK",
            RewardAmount = 500,
            RewardCurrency = Currency.Aigen,
            VerificationType = VerificationType.Oracle,
            VerificationParams = new VerificationParams { OracleDescription = "GitHub repo deliverable" },
            DeadlineHours = 48,
            // CreatorAgentId left null on purpose -> defaults from AgentId.
        });

        Assert.Equal("m-new", m.Id);
        Assert.NotNull(handler.LastCreate);
        Assert.Equal("agent.creator", handler.LastCreate!["creator_agent_id"]!.GetValue<string>());
        Assert.Equal(48, handler.LastCreate["deadline_hours"]!.GetValue<int>());
        Assert.Equal("AIGEN", handler.LastCreate["reward_currency"]!.GetValue<string>());
        Assert.Equal(500, handler.LastCreate["reward_amount"]!.GetValue<double>());
        Assert.Equal("oracle", handler.LastCreate["verification_type"]!.GetValue<string>());
        Assert.Equal("GitHub repo deliverable",
            handler.LastCreate["verification_params"]!["oracle_description"]!.GetValue<string>());
    }

    [Theory]
    [MemberData(nameof(InvalidCreateRequests))]
    public async Task CreateMission_validates_locally_without_network(CreateMissionRequest req)
    {
        // No handler call should happen; use a handler that would throw if hit.
        using var client = NewClient(new StaticHandler(HttpStatusCode.InternalServerError, "{}"));
        await Assert.ThrowsAsync<ArgumentException>(() => client.CreateMissionAsync(req));
    }

    public static IEnumerable<object[]> InvalidCreateRequests()
    {
        yield return new object[] { new CreateMissionRequest { Title = "x", RewardAmount = 1, RewardCurrency = Currency.Aigen, VerificationType = VerificationType.Oracle, DeadlineHours = 1 } }; // missing creator (no AgentId set)
        yield return new object[] { new CreateMissionRequest { CreatorAgentId = "a", RewardAmount = 1, RewardCurrency = Currency.Aigen, VerificationType = VerificationType.Oracle, DeadlineHours = 1 } }; // missing title
        yield return new object[] { new CreateMissionRequest { CreatorAgentId = "a", Title = "x", RewardAmount = 0, RewardCurrency = Currency.Aigen, VerificationType = VerificationType.Oracle, DeadlineHours = 1 } }; // bad reward
        yield return new object[] { new CreateMissionRequest { CreatorAgentId = "a", Title = "x", RewardAmount = 1, RewardCurrency = new Currency(""), VerificationType = VerificationType.Oracle, DeadlineHours = 1 } }; // missing currency
        yield return new object[] { new CreateMissionRequest { CreatorAgentId = "a", Title = "x", RewardAmount = 1, RewardCurrency = Currency.Aigen, VerificationType = VerificationType.Oracle, DeadlineHours = 0 } }; // bad deadline
        yield return new object[] { new CreateMissionRequest { CreatorAgentId = "a", Title = "x", RewardAmount = 1, RewardCurrency = Currency.Aigen, VerificationType = VerificationType.FirstValidMatch, DeadlineHours = 1 } }; // regex required
    }

    [Fact]
    public async Task Submit_hits_no_api_prefix_path_and_defaults_agent()
    {
        var handler = new FakeApiHandler();
        using var client = NewClient(handler, agentId: "agent.alice");

        SubmitResult res = await client.SubmitAsync("m-2", new SubmitRequest { Proof = "deadbeef" });

        Assert.True(res.Accepted);
        Assert.Equal("deadbeef", res.Submission!.Proof);
        // The endpoint must NOT carry an /api prefix.
        Assert.Equal("/missions/m-2/submit", handler.LastPath);
        Assert.Equal("agent.alice", handler.LastSubmit!["submitter_agent_id"]!.GetValue<string>());
        Assert.Equal("deadbeef", handler.LastSubmit["proof"]!.GetValue<string>());
    }

    [Fact]
    public async Task Submit_requires_agent_proof_and_mission_id()
    {
        var handler = new FakeApiHandler();
        using var noAgent = NewClient(handler);
        await Assert.ThrowsAsync<ArgumentException>(
            () => noAgent.SubmitAsync("m-2", new SubmitRequest { Proof = "x" }));

        using var client = NewClient(handler, agentId: "a");
        await Assert.ThrowsAsync<ArgumentException>(
            () => client.SubmitAsync("m-2", new SubmitRequest { Proof = "" }));
        await Assert.ThrowsAsync<ArgumentException>(
            () => client.SubmitAsync("", new SubmitRequest { Proof = "x" }));
    }

    [Fact]
    public async Task GetStats_decodes_counters()
    {
        var handler = new FakeApiHandler();
        using var client = NewClient(handler);

        Stats s = await client.GetStatsAsync();

        Assert.Equal(3, s.Open);
        Assert.Equal(12, s.Resolved);
        Assert.Equal(108000, s.LifetimeRewardAigenPaid);
    }

    [Fact]
    public async Task GetReputation_defaults_agent_and_preserves_extra()
    {
        var handler = new FakeApiHandler();
        using var client = NewClient(handler, agentId: "agent.alice");

        Reputation rep = await client.GetReputationAsync(); // null -> defaults to AgentId

        Assert.Equal("agent.alice", rep.AgentId);
        Assert.Equal(4200.5, rep.AigenBalance);
        Assert.Equal(7, rep.MissionsWon);
        Assert.NotNull(rep.Extra);
        Assert.True(rep.Extra!.ContainsKey("streak_days"));

        using var noAgent = NewClient(handler);
        await Assert.ThrowsAsync<ArgumentException>(() => noAgent.GetReputationAsync());
    }

    [Fact]
    public async Task ApiKey_is_sent_as_bearer_header()
    {
        var handler = new FakeApiHandler();
        using var client = NewClient(handler, apiKey: "tok123");

        await client.GetStatsAsync();

        Assert.Equal("Bearer tok123", handler.LastAuthorization);
        Assert.Contains("oabp-dotnet", handler.LastUserAgent);
    }

    [Fact]
    public async Task ServerError_maps_to_api_exception_with_message()
    {
        using var client = NewClient(new StaticHandler(HttpStatusCode.InternalServerError, """{"error":"boom"}"""));

        OabpApiException ex = await Assert.ThrowsAsync<OabpApiException>(() => client.GetStatsAsync());

        Assert.Equal((HttpStatusCode)500, ex.StatusCode);
        Assert.Equal("boom", ex.ResponseMessage);
        Assert.Contains("boom", ex.Message);
    }

    [Fact]
    public async Task Cancellation_token_is_honored()
    {
        using var client = NewClient(new BlockingHandler());
        using var cts = new CancellationTokenSource(TimeSpan.FromMilliseconds(50));

        await Assert.ThrowsAnyAsync<OperationCanceledException>(
            () => client.ListMissionsAsync(cts.Token));
    }

    [Fact]
    public void Options_and_base_url_are_normalized()
    {
        using var client = new OabpClient(new OabpClientOptions
        {
            BaseUrl = "https://example.test/",
            AgentId = "agent.x",
        });
        Assert.Equal("https://example.test", client.BaseUrl);
        Assert.Equal("agent.x", client.AgentId);
    }

    [Fact]
    public void Mission_is_expired_reflects_deadline()
    {
        var past = new Mission { Deadline = DateTimeOffset.UtcNow.AddHours(-1) };
        var future = new Mission { Deadline = DateTimeOffset.UtcNow.AddHours(1) };
        var none = new Mission { Deadline = null };

        Assert.True(past.IsExpired);
        Assert.False(future.IsExpired);
        Assert.False(none.IsExpired);
    }

    [Fact]
    public void Default_constructor_targets_public_deployment()
    {
        using var client = new OabpClient();
        Assert.Equal("https://cryptogenesis.duckdns.org", client.BaseUrl);
    }
}
