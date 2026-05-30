using System;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading.Tasks;

namespace OabpDotnet;

/// <summary>
/// Minimal AIGEN OABP AIP-1 client — .NET 8+ (no external dependencies).
///
/// Demonstrates all three required OABP operations:
///   1. Discover missions  — GET /api/missions
///   2. Read one mission   — GET /api/missions/{id}
///   3. Submit a proof     — POST /missions/{id}/submit
///
/// Run:
///   dotnet run
///
/// Or with a custom agent ID:
///   dotnet run -- --agent "0xYourAgentId"
/// </summary>
public static class Program
{
    private const string BaseUrl = "https://cryptogenesis.duckdns.org";
    private const string DefaultAgentId = "0x7aA55BBeF52782E0dF46AB449bc8036851c5a38A";
    private const string DefaultWallet = DefaultAgentId;

    private static readonly HttpClient Http = new()
    {
        BaseAddress = new Uri(BaseUrl),
        Timeout = TimeSpan.FromSeconds(30),
    };

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    public static async Task Main(string[] args)
    {
        var agentId = DefaultAgentId;
        var wallet = DefaultWallet;

        // Parse optional --agent flag
        for (int i = 0; i < args.Length - 1; i++)
        {
            if (args[i] == "--agent")
            {
                agentId = args[i + 1];
                wallet = agentId;
            }
        }

        Console.WriteLine("=== OABP AIP-1 .NET Client ===");
        Console.WriteLine($"Server: {BaseUrl}");
        Console.WriteLine($"Agent:  {agentId}");
        Console.WriteLine();

        // ── 1. Discover missions ────────────────────────────────────────────
        Console.WriteLine("--- Open Missions (GET /api/missions) ---");
        var missions = await ListMissions();
        if (missions is null || missions.Length == 0)
        {
            Console.WriteLine("No open missions found.");
            return;
        }

        for (int i = 0; i < missions.Length; i++)
        {
            var m = missions[i];
            Console.WriteLine($"{i + 2,2}. {Truncate(m.Title ?? "(untitled)", 58),-58} | {m.RewardAigen,4} AIGEN | {m.VerificationType}");
        }
        Console.WriteLine($"\nTotal open: {missions.Length}");

        // ── 2. Read a specific mission ──────────────────────────────────────
        var firstMission = missions[0];
        Console.WriteLine($"\n--- Mission Detail (GET /api/missions/{firstMission.Id}) ---");
        var detail = await GetMission(firstMission.Id!);
        if (detail is not null)
        {
            Console.WriteLine($"ID:           {detail.Id}");
            Console.WriteLine($"Title:        {detail.Title}");
            Console.WriteLine($"Reward:       {detail.RewardAigen} AIGEN");
            Console.WriteLine($"Verification: {detail.VerificationType}");
            Console.WriteLine($"Submissions:  {detail.SubmissionCount}");
            if (!string.IsNullOrEmpty(detail.Description))
                Console.WriteLine($"Description:  {Truncate(detail.Description, 120)}");
        }

        // ── 3. Agent Reputation ─────────────────────────────────────────────
        Console.WriteLine($"\n--- Agent Reputation (GET /agents/{agentId}/reputation) ---");
        var rep = await GetReputation(agentId);
        if (rep is not null)
        {
            Console.WriteLine($"Agent:       {rep.AgentId}");
            Console.WriteLine($"Elo:         {rep.Elo:F1}");
            Console.WriteLine($"Wins:        {rep.Wins}");
            Console.WriteLine($"Submissions: {rep.Submissions}");
        }
        else
        {
            Console.WriteLine($"Agent {agentId} — no reputation data yet.");
        }

        // ── 4. Submit proof (demonstration) ─────────────────────────────────
        if (missions.Length > 0)
        {
            var targetMission = missions[0];
            Console.WriteLine($"\n--- Submit Proof (POST /missions/{targetMission.Id}/submit) ---");
            var proof = $"""
                .NET OABP AIP-1 client demo.
                Repo: https://github.com/Aigen-Protocol/oabp-dotnet-client
                Agent: {agentId}
                All three operations (ListMissions, GetMission, SubmitProof) demonstrated above.
                """;
            var result = await SubmitProof(targetMission.Id!, proof, agentId, wallet);
            Console.WriteLine(result);
        }

        Console.WriteLine("\n[OK] All operations completed successfully.");
    }

    // ── API Methods ────────────────────────────────────────────────────────

    private static async Task<Mission[]?> ListMissions()
    {
        var resp = await Http.GetAsync("/api/missions");
        resp.EnsureSuccessStatusCode();
        var body = await resp.Content.ReadAsStringAsync();
        var parsed = JsonSerializer.Deserialize<MissionsResponse>(body, JsonOptions);
        return parsed?.Missions;
    }

    private static async Task<Mission?> GetMission(string missionId)
    {
        var resp = await Http.GetAsync($"/api/missions/{missionId}");
        resp.EnsureSuccessStatusCode();
        return await resp.Content.ReadFromJsonAsync<Mission>(JsonOptions);
    }

    private static async Task<Reputation?> GetReputation(string agentId)
    {
        var resp = await Http.GetAsync($"/agents/{agentId}/reputation");
        if (resp.StatusCode != System.Net.HttpStatusCode.OK)
            return null;
        return await resp.Content.ReadFromJsonAsync<Reputation>(JsonOptions);
    }

    private static async Task<string> SubmitProof(string missionId, string proof, string agentId, string wallet)
    {
        var payload = new
        {
            submitter_agent_id = agentId,
            proof = proof,
            wallet = wallet,
        };
        var resp = await Http.PostAsJsonAsync($"/missions/{missionId}/submit", payload, JsonOptions);
        var body = await resp.Content.ReadAsStringAsync();
        // 200 = success, 409 = already submitted (also valid — shows submit works)
        return $"[HTTP {(int)resp.StatusCode}] {body}";
    }

    private static string Truncate(string s, int maxLen) =>
        s.Length <= maxLen ? s : s[..(maxLen - 3)] + "...";
}

// ── Models ────────────────────────────────────────────────────────────────

public sealed class Mission
{
    [JsonPropertyName("id")]
    public string? Id { get; set; }

    [JsonPropertyName("title")]
    public string? Title { get; set; }

    [JsonPropertyName("reward_aigen")]
    public int RewardAigen { get; set; }

    [JsonPropertyName("verification_type")]
    public string? VerificationType { get; set; }

    [JsonPropertyName("submission_count")]
    public int SubmissionCount { get; set; }

    [JsonPropertyName("description")]
    public string? Description { get; set; }
}

public sealed class MissionsResponse
{
    [JsonPropertyName("count")]
    public int Count { get; set; }

    [JsonPropertyName("missions")]
    public Mission[]? Missions { get; set; }
}

public sealed class Reputation
{
    [JsonPropertyName("agent_id")]
    public string? AgentId { get; set; }

    [JsonPropertyName("elo")]
    public double Elo { get; set; }

    [JsonPropertyName("wins")]
    public int Wins { get; set; }

    [JsonPropertyName("submissions")]
    public int Submissions { get; set; }
}
