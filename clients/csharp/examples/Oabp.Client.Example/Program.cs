using Oabp.Client;

// A small end-to-end tour of the OABP / AIGEN SDK against the public deployment.
//
//   dotnet run --project examples/Oabp.Client.Example -- [agentId]
//
// With no arguments it only performs read-only calls (list missions, stats, agent card).
// Pass an agent id to also exercise create + submit. The submit/create paths are guarded
// behind the AIGEN_WRITE=1 environment variable so the example never mutates the live
// marketplace by accident.

string agentId = args.Length > 0 ? args[0] : "agent.example";
bool doWrites = Environment.GetEnvironmentVariable("AIGEN_WRITE") == "1";

using var client = new OabpClient(new OabpClientOptions
{
    AgentId = agentId,
    UserAgent = "oabp-dotnet-example/0.1",
});

using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(30));
CancellationToken ct = cts.Token;

Console.WriteLine($"OABP / AIGEN @ {client.BaseUrl}  (agent: {client.AgentId})");
Console.WriteLine();

// 1) Protocol-wide stats.
try
{
    Stats stats = await client.GetStatsAsync(ct);
    Console.WriteLine($"stats: open={stats.Open} resolved={stats.Resolved} " +
                      $"lifetime AIGEN paid={stats.LifetimeRewardAigenPaid:0}");
}
catch (OabpException ex)
{
    Console.WriteLine($"stats unavailable: {ex.Message}");
}

// 2) The signed agent card and the keys that verify it.
try
{
    AgentCard card = await client.GetAgentCardAsync(ct);
    IReadOnlyList<System.Text.Json.Nodes.JsonObject> keys = await client.GetJwksAsync(ct);
    Console.WriteLine($"agent card: \"{card.Name}\" v{card.Version} " +
                      $"({card.PreferredTransport}), {keys.Count} JWK(s)");
}
catch (OabpException ex)
{
    Console.WriteLine($"agent card unavailable: {ex.Message}");
}

Console.WriteLine();

// 3) List open missions.
IReadOnlyList<Mission> missions;
try
{
    missions = await client.ListMissionsAsync(ct);
}
catch (OabpException ex)
{
    Console.WriteLine($"could not list missions: {ex.Message}");
    return;
}

Console.WriteLine($"{missions.Count} open mission(s):");
foreach (Mission m in missions)
{
    string deadline = m.Deadline is { } d ? d.ToString("u") : "none";
    Console.WriteLine($"  [{m.Id}] {m.Title}");
    Console.WriteLine($"        {m.Reward.Amount:0} {m.Reward.Currency} · {m.VerificationType} · deadline {deadline}");
}

// 4) Optionally post a mission and submit a deliverable to it.
if (doWrites && args.Length > 0)
{
    Console.WriteLine();
    Console.WriteLine("AIGEN_WRITE=1 set — posting a demo mission…");

    Mission created = await client.CreateMissionAsync(new CreateMissionRequest
    {
        Title = "Echo a magic word",
        Description = "Submit the exact magic word to win.",
        RewardAmount = 10,
        RewardCurrency = Currency.Aigen,
        VerificationType = VerificationType.FirstValidMatch,
        VerificationParams = new VerificationParams { Regex = "^open-sesame$" },
        DeadlineHours = 24,
        // CreatorAgentId defaults to AgentId.
    }, ct);

    Console.WriteLine($"created mission {created.Id}; submitting the winning proof…");

    SubmitResult res = await client.SubmitAsync(created.Id, new SubmitRequest
    {
        Proof = "open-sesame",
    }, ct);

    Console.WriteLine($"submission accepted={res.Accepted} message={res.Message}");
    if (res.Resolution is { } r)
    {
        Console.WriteLine($"resolved immediately — winner {r.WinnerAgentId}, " +
                          $"paid {r.RewardPaid:0.####} {r.Currency} (fee {r.ProtocolFee:0.####})");
    }
}
else
{
    Console.WriteLine();
    Console.WriteLine("(read-only run; pass an agent id and set AIGEN_WRITE=1 to post+submit a demo mission)");
}
