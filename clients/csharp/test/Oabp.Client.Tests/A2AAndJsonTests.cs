using System.Text.Json;
using System.Text.Json.Nodes;
using Xunit;

namespace Oabp.Client.Tests;

public sealed class A2AAndJsonTests
{
    private const string BaseUrl = "https://api.test.local";

    private static OabpClient NewClient(HttpMessageHandler handler)
        => new(new HttpClient(handler), new OabpClientOptions { BaseUrl = BaseUrl });

    [Fact]
    public async Task SendMessage_posts_jsonrpc_envelope_and_returns_result()
    {
        var handler = new FakeApiHandler();
        using var client = NewClient(handler);

        JsonNode? result = await client.SendMessageAsync(A2AMessage.Text("hello agent"));

        Assert.NotNull(handler.LastRpc);
        Assert.Equal("2.0", handler.LastRpc!["jsonrpc"]!.GetValue<string>());
        Assert.Equal("message/send", handler.LastRpc["method"]!.GetValue<string>());
        // The message must be nested under params.message with a text part.
        JsonNode part = handler.LastRpc["params"]!["message"]!["parts"]![0]!;
        Assert.Equal("text", part["kind"]!.GetValue<string>());
        Assert.Equal("hello agent", part["text"]!.GetValue<string>());

        Assert.NotNull(result);
        Assert.Equal("task-1", result!["id"]!.GetValue<string>());
    }

    [Fact]
    public async Task GetTask_and_ListTasks_decode()
    {
        var handler = new FakeApiHandler();
        using var client = NewClient(handler);

        A2ATask? task = await client.GetTaskAsync("task-1");
        Assert.NotNull(task);
        Assert.Equal("task-1", task!.Id);
        Assert.NotNull(task.Status);
        Assert.Equal("completed", task.Status!["state"]!.GetValue<string>());
        Assert.True(task.Raw.ContainsKey("status"));

        IReadOnlyList<A2ATask> tasks = await client.ListTasksAsync();
        Assert.Equal(2, tasks.Count);
        Assert.Equal("task-2", tasks[1].Id);
    }

    [Fact]
    public void ListTasks_accepts_wrapped_object_shape()
    {
        // Some deployments wrap the array in {"tasks":[...]} — the parser handles both.
        JsonNode wrapped = JsonNode.Parse("""{"tasks":[{"id":"t-1"},{"id":"t-2"}]}""")!;
        IReadOnlyList<A2ATask> tasks = OabpClient.ParseTaskList(wrapped);
        Assert.Equal(2, tasks.Count);
        Assert.Equal("t-2", tasks[1].Id);
    }

    [Fact]
    public async Task A2A_rpc_error_is_thrown()
    {
        var handler = new FakeApiHandler();
        using var client = NewClient(handler);

        OabpRpcException ex = await Assert.ThrowsAsync<OabpRpcException>(
            () => client.A2ACallRawAsync("does/not/exist", new { }));

        Assert.Equal(-32601, ex.Code);
        Assert.Contains("method not found", ex.RpcMessage);
    }

    [Fact]
    public async Task AgentCard_and_Jwks_decode_and_preserve_raw()
    {
        var handler = new FakeApiHandler();
        using var client = NewClient(handler);

        AgentCard card = await client.GetAgentCardAsync();
        Assert.Equal("AIGEN OABP Agent", card.Name);
        Assert.Equal("JSONRPC", card.PreferredTransport);
        Assert.Equal("0.3.0", card.ProtocolVersion);
        // Raw retains the full signed document, incl. fields the SDK does not model.
        Assert.True(card.Raw.ContainsKey("capabilities"));

        IReadOnlyList<JsonObject> keys = await client.GetJwksAsync();
        JsonObject key = Assert.Single(keys);
        Assert.Equal("ES256", key["alg"]!.GetValue<string>());
        Assert.Equal("k1", key["kid"]!.GetValue<string>());
    }

    [Theory]
    [InlineData("1700000000", 1700000000L)]
    [InlineData("\"1700000000\"", 1700000000L)] // numeric string
    [InlineData("1700000000.5", 1700000000L)]   // fractional second, whole part preserved
    [InlineData("0", 0L)]                         // epoch is a real time
    public void UnixTimeConverter_reads_various_shapes(string json, long expectedSeconds)
    {
        var opts = new JsonSerializerOptions();
        opts.Converters.Add(new UnixTimeConverter());

        DateTimeOffset? dto = JsonSerializer.Deserialize<DateTimeOffset?>(json, opts);

        Assert.NotNull(dto);
        Assert.Equal(expectedSeconds, dto!.Value.ToUnixTimeSeconds());
    }

    [Fact]
    public void UnixTimeConverter_reads_null_as_null_and_round_trips()
    {
        var opts = new JsonSerializerOptions();
        opts.Converters.Add(new UnixTimeConverter());

        Assert.Null(JsonSerializer.Deserialize<DateTimeOffset?>("null", opts));

        var t = DateTimeOffset.FromUnixTimeSeconds(1893456000);
        string json = JsonSerializer.Serialize<DateTimeOffset?>(t, opts);
        Assert.Equal("1893456000", json);
    }

    [Fact]
    public void Open_enums_preserve_unknown_values()
    {
        // An unknown currency the protocol might add later must not break deserialization.
        Mission m = JsonSerializer.Deserialize<Mission>("""
        {"id":"x","title":"t","description":"d",
         "reward":{"amount":1,"currency":"ETH"},
         "verification_type":"future_mode",
         "verification_params":{},
         "deadline":1893456000,"status":"open","submissions":[]}
        """, JsonDefaults.Options)!;

        Assert.Equal("ETH", m.Reward.Currency.Value);
        Assert.Equal("future_mode", m.VerificationType.Value);
        // Known constants still compare by value.
        Assert.Equal(Currency.Usdc, Currency.Of("USDC"));
        Assert.NotEqual(Currency.Aigen, m.Reward.Currency);
    }

    [Fact]
    public void CreateMission_request_serializes_to_documented_field_names()
    {
        var req = new CreateMissionRequest
        {
            CreatorAgentId = "agent.x",
            Title = "t",
            Description = "d",
            RewardAmount = 250,
            RewardCurrency = Currency.Aigen,
            VerificationType = VerificationType.FirstValidMatch,
            VerificationParams = new VerificationParams { Regex = "^x$" },
            DeadlineHours = 24,
        };

        JsonNode node = JsonSerializer.SerializeToNode(req, JsonDefaults.Options)!;

        Assert.Equal("agent.x", node["creator_agent_id"]!.GetValue<string>());
        Assert.Equal(250, node["reward_amount"]!.GetValue<double>());
        Assert.Equal("AIGEN", node["reward_currency"]!.GetValue<string>());
        Assert.Equal("first_valid_match", node["verification_type"]!.GetValue<string>());
        Assert.Equal("^x$", node["verification_params"]!["regex"]!.GetValue<string>());
        Assert.Equal(24, node["deadline_hours"]!.GetValue<int>());
        // Null oracle_description must be omitted (WhenWritingNull).
        Assert.Null(node["verification_params"]!["oracle_description"]);
    }
}
