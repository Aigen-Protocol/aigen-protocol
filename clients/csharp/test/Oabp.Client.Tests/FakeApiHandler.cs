using System.Net;
using System.Text;
using System.Text.Json.Nodes;

namespace Oabp.Client.Tests;

/// <summary>
/// An in-memory <see cref="HttpMessageHandler"/> implementing just enough of the documented
/// OABP / AIGEN API to assert that <see cref="OabpClient"/> speaks the wire protocol
/// correctly. It records the last request method/path/body and the last JSON-RPC envelope so
/// tests can verify what the SDK actually sent.
/// </summary>
public sealed class FakeApiHandler : HttpMessageHandler
{
    /// <summary>Unix seconds the create endpoint echoes back as the deadline.</summary>
    public long EchoDeadline { get; } = DateTimeOffset.UtcNow.AddHours(24).ToUnixTimeSeconds();

    public string? LastMethod { get; private set; }
    public string? LastPath { get; private set; }
    public string? LastBody { get; private set; }
    public string? LastAuthorization { get; private set; }
    public string? LastUserAgent { get; private set; }
    public JsonObject? LastRpc { get; private set; }
    public JsonObject? LastCreate { get; private set; }
    public JsonObject? LastSubmit { get; private set; }

    protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        LastMethod = request.Method.Method;
        LastPath = request.RequestUri!.AbsolutePath;
        LastAuthorization = request.Headers.Authorization?.ToString();
        LastUserAgent = request.Headers.UserAgent.ToString();
        LastBody = request.Content is null ? null : await request.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);

        string method = request.Method.Method;
        string path = LastPath;

        // POST /missions/{id}/submit  (note: no /api prefix)
        if (method == "POST" && path.StartsWith("/missions/") && path.EndsWith("/submit"))
        {
            LastSubmit = JsonNode.Parse(LastBody!)!.AsObject();
            string submitter = LastSubmit["submitter_agent_id"]?.GetValue<string>() ?? "";
            string proof = LastSubmit["proof"]?.GetValue<string>() ?? "";
            return Json(HttpStatusCode.OK, $$"""
            {
              "accepted": true,
              "submission": {"id": "s-1", "submitter_agent_id": {{Quote(submitter)}}, "proof": {{Quote(proof)}}},
              "message": "queued for verification"
            }
            """);
        }

        // /api/missions  (GET list, POST create)
        if (path == "/api/missions")
        {
            if (method == "GET")
            {
                return Json(HttpStatusCode.OK, OpenMissionsJson());
            }
            if (method == "POST")
            {
                LastCreate = JsonNode.Parse(LastBody!)!.AsObject();
                var c = LastCreate;
                return Json(HttpStatusCode.Created, $$"""
                {
                  "id": "m-new",
                  "title": {{Quote(c["title"]?.GetValue<string>() ?? "")}},
                  "description": {{Quote(c["description"]?.GetValue<string>() ?? "")}},
                  "reward": {"amount": {{c["reward_amount"]}}, "currency": {{Quote(c["reward_currency"]?.GetValue<string>() ?? "AIGEN")}}},
                  "verification_type": {{Quote(c["verification_type"]?.GetValue<string>() ?? "")}},
                  "verification_params": {{(c["verification_params"]?.ToJsonString() ?? "{}")}},
                  "deadline": {{EchoDeadline}},
                  "status": "open",
                  "creator_agent_id": {{Quote(c["creator_agent_id"]?.GetValue<string>() ?? "")}},
                  "submissions": []
                }
                """);
            }
        }

        // GET /api/missions/{id}
        if (method == "GET" && path.StartsWith("/api/missions/"))
        {
            string id = path["/api/missions/".Length..];
            if (id == "m-1")
            {
                return Json(HttpStatusCode.OK, MissionDetailJson);
            }
            return Json(HttpStatusCode.NotFound, """{"error": "mission not found"}""");
        }

        // GET /api/stats
        if (method == "GET" && path == "/api/stats")
        {
            return Json(HttpStatusCode.OK, """{"resolved": 12, "open": 3, "lifetime_reward_aigen_paid": 108000}""");
        }

        // GET /api/reputation/{agent}
        if (method == "GET" && path.StartsWith("/api/reputation/"))
        {
            string agent = path["/api/reputation/".Length..];
            // Includes an undocumented "streak_days" field to prove Extra capture.
            return Json(HttpStatusCode.OK, $$"""
            {"agent_id": {{Quote(agent)}}, "aigen_balance": 4200.5, "missions_won": 7, "streak_days": 9}
            """);
        }

        // POST /api/a2a  (JSON-RPC 2.0)
        if (method == "POST" && path == "/api/a2a")
        {
            LastRpc = JsonNode.Parse(LastBody!)!.AsObject();
            string rpcMethod = LastRpc["method"]?.GetValue<string>() ?? "";
            string idJson = (LastRpc["id"]?.DeepClone() ?? 0).ToJsonString();
            string result = rpcMethod switch
            {
                "message/send" => """{"id": "task-1", "status": {"state": "submitted"}}""",
                "tasks/get" => """{"id": "task-1", "status": {"state": "completed"}}""",
                "tasks/list" => """[{"id": "task-1", "status": {"state": "completed"}}, {"id": "task-2", "status": {"state": "working"}}]""",
                _ => "",
            };
            string envelope = result.Length == 0
                ? "{\"jsonrpc\": \"2.0\", \"id\": " + idJson + ", \"error\": {\"code\": -32601, \"message\": \"method not found\"}}"
                : "{\"jsonrpc\": \"2.0\", \"id\": " + idJson + ", \"result\": " + result + "}";
            return Json(HttpStatusCode.OK, envelope);
        }

        // well-known documents
        if (method == "GET" && path == "/.well-known/agent-card.json")
        {
            return Json(HttpStatusCode.OK, """
            {
              "name": "AIGEN OABP Agent",
              "description": "agent-bounty marketplace",
              "url": "https://cryptogenesis.duckdns.org/api/a2a",
              "version": "1.0.0",
              "protocolVersion": "0.3.0",
              "preferredTransport": "JSONRPC",
              "capabilities": {"streaming": false}
            }
            """);
        }
        if (method == "GET" && path == "/.well-known/jwks.json")
        {
            return Json(HttpStatusCode.OK, """{"keys": [{"kty": "EC", "crv": "P-256", "x": "abc", "y": "def", "kid": "k1", "alg": "ES256"}]}""");
        }

        return Json(HttpStatusCode.NotFound, """{"error": "not found"}""");
    }

    private string OpenMissionsJson() => $$"""
    [
      {
        "id": "m-1",
        "title": "Safety review of token 0xabc",
        "description": "GoPlus token-security review",
        "reward": {"amount": 250, "currency": "AIGEN"},
        "verification_type": "oracle",
        "verification_params": {"oracle_description": "GoPlus safety review of 0xabc"},
        "deadline": {{EchoDeadline}},
        "status": "open",
        "submissions": []
      },
      {
        "id": "m-2",
        "title": "SHA-256 puzzle",
        "description": "match the regex",
        "reward": {"amount": 1000, "currency": "USDC"},
        "verification_type": "first_valid_match",
        "verification_params": {"regex": "^[a-f0-9]{64}$"},
        "deadline": {{EchoDeadline}},
        "status": "open",
        "submissions": []
      }
    ]
    """;

    // A hand-written detail payload: unix-seconds deadline, inline submission with an
    // undocumented "score" field, and a resolution showing the 0.5% fee.
    public const string MissionDetailJson = """
    {
      "id": "m-1",
      "title": "Safety review of token 0xabc",
      "description": "GoPlus token-security review",
      "reward": {"amount": 250, "currency": "AIGEN"},
      "verification_type": "oracle",
      "verification_params": {"oracle_description": "GoPlus safety review of 0xabc"},
      "deadline": 1893456000,
      "status": "resolved",
      "creator_agent_id": "agent.bob",
      "submissions": [
        {"id": "s-9", "submitter_agent_id": "agent.alice", "proof": "0xabc", "verified": true, "created_at": 1700000000, "score": 0.98}
      ],
      "resolution": {
        "status": "resolved",
        "winner_agent_id": "agent.alice",
        "reward_paid": 248.75,
        "currency": "AIGEN",
        "protocol_fee": 1.25,
        "resolved_at": 1700000500
      }
    }
    """;

    private static HttpResponseMessage Json(HttpStatusCode code, string body) => new(code)
    {
        Content = new StringContent(body, Encoding.UTF8, "application/json"),
    };

    private static string Quote(string s) => System.Text.Json.JsonSerializer.Serialize(s);
}

/// <summary>
/// A trivial handler whose <see cref="SendAsync"/> blocks until the request is cancelled,
/// used to test <see cref="CancellationToken"/> propagation.
/// </summary>
public sealed class BlockingHandler : HttpMessageHandler
{
    protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        var tcs = new TaskCompletionSource();
        using (cancellationToken.Register(() => tcs.TrySetResult()))
        {
            await tcs.Task.ConfigureAwait(false);
        }
        cancellationToken.ThrowIfCancellationRequested();
        return new HttpResponseMessage(HttpStatusCode.OK);
    }
}

/// <summary>A handler that always returns a fixed status and body, for error-path tests.</summary>
public sealed class StaticHandler(HttpStatusCode code, string body) : HttpMessageHandler
{
    public string? LastAuthorization { get; private set; }

    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        LastAuthorization = request.Headers.Authorization?.ToString();
        return Task.FromResult(new HttpResponseMessage(code)
        {
            Content = new StringContent(body, Encoding.UTF8, "application/json"),
        });
    }
}
