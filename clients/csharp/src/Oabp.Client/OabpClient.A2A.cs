using System.Net;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.Json.Serialization;

namespace Oabp.Client;

/// <summary>
/// A2A (Agent-to-Agent) JSON-RPC 2.0 surface: <c>POST /api/a2a</c>, plus the discovery
/// documents — the ES256-signed agent card and the JWKS used to verify it.
/// </summary>
public sealed partial class OabpClient
{
    /// <summary>JSON-RPC method: send a message to the agent.</summary>
    public const string A2AMethodMessageSend = "message/send";

    /// <summary>JSON-RPC method: fetch a task by id.</summary>
    public const string A2AMethodTasksGet = "tasks/get";

    /// <summary>JSON-RPC method: list tasks.</summary>
    public const string A2AMethodTasksList = "tasks/list";

    private const string PathA2A = "/api/a2a";
    private static int _rpcId; // monotonically increasing across all clients; uniqueness per call suffices

    /// <summary>
    /// Performs a raw JSON-RPC 2.0 call against the A2A endpoint and deserializes the
    /// <c>result</c> into <typeparamref name="TResult"/>. A JSON-RPC <c>error</c> object is
    /// raised as an <see cref="OabpRpcException"/>.
    /// </summary>
    /// <remarks>
    /// Most callers should prefer the typed helpers (<see cref="SendMessageAsync(A2AMessage, CancellationToken)"/>,
    /// <see cref="GetTaskAsync"/>, <see cref="ListTasksAsync"/>); this method is exposed for
    /// forward-compatibility with methods this SDK version does not yet model.
    /// </remarks>
    public async Task<TResult?> A2ACallAsync<TResult>(string method, object? @params, CancellationToken cancellationToken = default)
    {
        JsonNode? result = await A2ACallRawAsync(method, @params, cancellationToken).ConfigureAwait(false);
        if (result is null)
        {
            return default;
        }
        return result.Deserialize<TResult>(JsonDefaults.Options);
    }

    /// <summary>
    /// Performs a raw JSON-RPC 2.0 call and returns the <c>result</c> as a
    /// <see cref="JsonNode"/> (or <c>null</c> when absent), so callers can inspect or decode
    /// whichever shape the agent returned.
    /// </summary>
    public async Task<JsonNode?> A2ACallRawAsync(string method, object? @params, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrEmpty(method))
        {
            throw new ArgumentException("JSON-RPC method is required.", nameof(method));
        }

        int id = Interlocked.Increment(ref _rpcId);
        var envelope = new JsonObject
        {
            ["jsonrpc"] = "2.0",
            ["id"] = id,
            ["method"] = method,
        };
        if (@params is not null)
        {
            envelope["params"] = JsonSerializer.SerializeToNode(@params, @params.GetType(), JsonDefaults.Options);
        }

        JsonNode response = await PostJsonNodeAsync(PathA2A, envelope, cancellationToken).ConfigureAwait(false)
            ?? throw new OabpTransportException($"oabp a2a: empty response for {method}", new InvalidOperationException());

        if (response is not JsonObject obj)
        {
            throw new OabpTransportException($"oabp a2a: non-object response for {method}", new InvalidOperationException());
        }
        if (obj.TryGetPropertyValue("error", out JsonNode? err) && err is JsonObject errObj)
        {
            int code = errObj.TryGetPropertyValue("code", out JsonNode? c) && c is not null ? c.GetValue<int>() : 0;
            string msg = errObj.TryGetPropertyValue("message", out JsonNode? m) && m is not null ? m.GetValue<string>() : "error";
            string? data = errObj.TryGetPropertyValue("data", out JsonNode? d) && d is not null ? d.ToJsonString() : null;
            throw new OabpRpcException(code, msg, data);
        }
        return obj.TryGetPropertyValue("result", out JsonNode? res) ? res : null;
    }

    /// <summary>
    /// Invokes <c>message/send</c> and returns the raw result. Per the A2A spec the result is
    /// either a Message or a Task depending on the agent; the <see cref="JsonNode"/> is
    /// returned verbatim so the caller can decode whichever they expect.
    /// </summary>
    public Task<JsonNode?> SendMessageAsync(A2AMessage message, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(message);
        return A2ACallRawAsync(A2AMethodMessageSend, new { message }, cancellationToken);
    }

    /// <summary>Convenience overload of <see cref="SendMessageAsync(A2AMessage, CancellationToken)"/> for a single text part.</summary>
    public Task<JsonNode?> SendMessageAsync(string text, CancellationToken cancellationToken = default)
        => SendMessageAsync(A2AMessage.Text(text), cancellationToken);

    /// <summary>Invokes <c>tasks/get</c> for a given task id.</summary>
    public async Task<A2ATask?> GetTaskAsync(string taskId, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrEmpty(taskId))
        {
            throw new ArgumentException("Task id is required.", nameof(taskId));
        }
        JsonNode? result = await A2ACallRawAsync(A2AMethodTasksGet, new { id = taskId }, cancellationToken).ConfigureAwait(false);
        return result is null ? null : A2ATask.FromNode(result);
    }

    /// <summary>
    /// Invokes <c>tasks/list</c> and returns the tasks. Both a bare array result and a
    /// <c>{"tasks":[...]}</c> wrapper are accepted.
    /// </summary>
    public async Task<IReadOnlyList<A2ATask>> ListTasksAsync(CancellationToken cancellationToken = default)
    {
        JsonNode? result = await A2ACallRawAsync(A2AMethodTasksList, new { }, cancellationToken).ConfigureAwait(false);
        return ParseTaskList(result);
    }

    internal static IReadOnlyList<A2ATask> ParseTaskList(JsonNode? result)
    {
        JsonArray? array = result switch
        {
            JsonArray arr => arr,
            JsonObject obj when obj.TryGetPropertyValue("tasks", out JsonNode? t) && t is JsonArray ta => ta,
            _ => null,
        };
        if (array is null)
        {
            return Array.Empty<A2ATask>();
        }
        var tasks = new List<A2ATask>(array.Count);
        foreach (JsonNode? node in array)
        {
            if (node is not null)
            {
                tasks.Add(A2ATask.FromNode(node));
            }
        }
        return tasks;
    }

    /// <summary>Fetches the ES256-signed agent card from <c>/.well-known/agent-card.json</c>.</summary>
    public async Task<AgentCard> GetAgentCardAsync(CancellationToken cancellationToken = default)
    {
        JsonNode node = await GetJsonNodeAsync("/.well-known/agent-card.json", cancellationToken).ConfigureAwait(false)
            ?? throw new OabpTransportException("oabp: empty agent card", new InvalidOperationException());
        return AgentCard.FromNode(node);
    }

    /// <summary>
    /// Fetches the JWKS used to verify the agent card's ES256 signature, from
    /// <c>/.well-known/jwks.json</c>. Keys are returned as raw <see cref="JsonObject"/>s so they
    /// can be fed to any JWK library.
    /// </summary>
    public async Task<IReadOnlyList<JsonObject>> GetJwksAsync(CancellationToken cancellationToken = default)
    {
        JsonNode? node = await GetJsonNodeAsync("/.well-known/jwks.json", cancellationToken).ConfigureAwait(false);
        if (node is JsonObject obj && obj.TryGetPropertyValue("keys", out JsonNode? keys) && keys is JsonArray arr)
        {
            var list = new List<JsonObject>(arr.Count);
            foreach (JsonNode? k in arr)
            {
                if (k is JsonObject ko)
                {
                    list.Add(ko);
                }
            }
            return list;
        }
        return Array.Empty<JsonObject>();
    }

    // --- low-level helpers returning JsonNode ---

    private Task<JsonNode?> GetJsonNodeAsync(string path, CancellationToken ct)
        => SendNodeAsync(HttpMethod.Get, path, body: null, ct);

    private Task<JsonNode?> PostJsonNodeAsync(string path, JsonNode body, CancellationToken ct)
        => SendNodeAsync(HttpMethod.Post, path, body, ct);

    private async Task<JsonNode?> SendNodeAsync(HttpMethod method, string path, JsonNode? body, CancellationToken ct)
    {
        using var request = new HttpRequestMessage(method, ResolveUri(path));
        request.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
        request.Headers.UserAgent.ParseAdd(_options.UserAgent);
        if (!string.IsNullOrEmpty(_options.ApiKey))
        {
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", _options.ApiKey);
        }
        if (body is not null)
        {
            request.Content = new StringContent(body.ToJsonString(JsonDefaults.Options), Encoding.UTF8, "application/json");
        }

        HttpResponseMessage response;
        try
        {
            response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, ct).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested)
        {
            throw;
        }
        catch (HttpRequestException ex)
        {
            throw new OabpTransportException($"oabp: {method} {path}: {ex.Message}", ex);
        }

        using (response)
        {
            string content = await ReadBodyAsync(response, ct).ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
            {
                throw new OabpApiException(response.StatusCode, method.Method, path, content);
            }
            if (string.IsNullOrWhiteSpace(content))
            {
                return null;
            }
            try
            {
                return JsonNode.Parse(content);
            }
            catch (JsonException ex)
            {
                throw new OabpTransportException($"oabp: {method} {path}: decode response: {ex.Message}", ex);
            }
        }
    }
}

/// <summary>
/// An A2A message: a role plus an ordered list of parts. Use <see cref="Text"/> for the
/// common single-text case.
/// </summary>
public sealed record A2AMessage
{
    /// <summary>Sender role (e.g. <c>user</c> or <c>agent</c>).</summary>
    [JsonPropertyName("role")]
    public string Role { get; init; } = "user";

    /// <summary>Ordered message parts.</summary>
    [JsonPropertyName("parts")]
    public IReadOnlyList<A2APart> Parts { get; init; } = Array.Empty<A2APart>();

    /// <summary>Optional client-generated message id.</summary>
    [JsonPropertyName("messageId")]
    public string? MessageId { get; init; }

    /// <summary>Builds a <c>user</c>-role message carrying a single text part.</summary>
    public static A2AMessage Text(string text) => new()
    {
        Role = "user",
        Parts = new[] { new A2APart { Kind = "text", Text = text } },
    };
}

/// <summary>One part of an A2A message. <see cref="Kind"/> is <c>text</c> for textual parts.</summary>
public sealed record A2APart
{
    /// <summary>Part kind, e.g. <c>text</c>.</summary>
    [JsonPropertyName("kind")]
    public string Kind { get; init; } = "text";

    /// <summary>Text content for <c>text</c> parts.</summary>
    [JsonPropertyName("text")]
    public string? Text { get; init; }
}

/// <summary>
/// A task returned by the A2A endpoint. The documented core (<see cref="Id"/> /
/// <see cref="Status"/>) is typed; the complete object is retained in <see cref="Raw"/> since
/// task shapes vary across implementations.
/// </summary>
public sealed record A2ATask
{
    /// <summary>Task id.</summary>
    public string Id { get; init; } = "";

    /// <summary>The task <c>status</c> object as raw JSON, when present.</summary>
    public JsonNode? Status { get; init; }

    /// <summary>The complete raw task object.</summary>
    public JsonObject Raw { get; init; } = new();

    internal static A2ATask FromNode(JsonNode node)
    {
        var obj = node as JsonObject ?? new JsonObject();
        return new A2ATask
        {
            Id = obj.TryGetPropertyValue("id", out JsonNode? id) && id is not null ? id.GetValue<string>() : "",
            Status = obj.TryGetPropertyValue("status", out JsonNode? st) ? st?.DeepClone() : null,
            Raw = (JsonObject)obj.DeepClone(),
        };
    }
}

/// <summary>
/// The (partial) A2A agent card describing this protocol's agent. Common fields are typed;
/// the complete <b>ES256-signed</b> document is retained in <see cref="Raw"/> so callers can
/// verify the JWS signature against the keys from <see cref="OabpClient.GetJwksAsync"/>.
/// </summary>
public sealed record AgentCard
{
    /// <summary>Agent display name.</summary>
    public string Name { get; init; } = "";

    /// <summary>Human description.</summary>
    public string? Description { get; init; }

    /// <summary>The A2A endpoint URL the card advertises.</summary>
    public string? Url { get; init; }

    /// <summary>Agent software version.</summary>
    public string? Version { get; init; }

    /// <summary>A2A protocol version.</summary>
    public string? ProtocolVersion { get; init; }

    /// <summary>Preferred transport (e.g. <c>JSONRPC</c>).</summary>
    public string? PreferredTransport { get; init; }

    /// <summary>The complete raw signed document, for ES256/JWS verification.</summary>
    public JsonObject Raw { get; init; } = new();

    internal static AgentCard FromNode(JsonNode node)
    {
        var obj = node as JsonObject ?? new JsonObject();
        string? Str(string key) => obj.TryGetPropertyValue(key, out JsonNode? n) && n is not null ? n.GetValue<string>() : null;
        return new AgentCard
        {
            Name = Str("name") ?? "",
            Description = Str("description"),
            Url = Str("url"),
            Version = Str("version"),
            ProtocolVersion = Str("protocolVersion"),
            PreferredTransport = Str("preferredTransport"),
            Raw = (JsonObject)obj.DeepClone(),
        };
    }
}
