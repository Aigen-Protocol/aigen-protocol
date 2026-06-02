using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;

namespace Oabp.Client;

/// <summary>
/// An async, thread-safe client for the OABP / AIGEN agent-bounty protocol.
/// </summary>
/// <remarks>
/// <para>
/// Create one instance and share it; it holds no per-call mutable state. With no options it
/// targets the public deployment (<see cref="OabpClientOptions.DefaultBaseUrl"/>). Every
/// network method is asynchronous and accepts a <see cref="CancellationToken"/>.
/// </para>
/// <para>
/// The client can either own an internal <see cref="HttpClient"/> (created for you, disposed
/// with the client) or wrap one you supply — useful for <c>IHttpClientFactory</c>, custom
/// handlers, or unit tests with a mocked <see cref="HttpMessageHandler"/>.
/// </para>
/// </remarks>
public sealed partial class OabpClient : IDisposable
{
    private readonly HttpClient _http;
    private readonly bool _ownsHttp;
    private readonly OabpClientOptions _options;
    private readonly Uri _baseUri;

    /// <summary>The configured base URL (trailing slash trimmed).</summary>
    public string BaseUrl => _baseUri.GetLeftPart(UriPartial.Path).TrimEnd('/');

    /// <summary>The configured calling-agent identity, if any.</summary>
    public string? AgentId => _options.AgentId;

    /// <summary>
    /// Creates a client that owns an internal <see cref="HttpClient"/> configured from
    /// <paramref name="options"/> (or defaults). The internal client is disposed when this
    /// client is disposed.
    /// </summary>
    public OabpClient(OabpClientOptions? options = null)
        : this(options ?? new OabpClientOptions(), CreateDefaultHttpClient(options ?? new OabpClientOptions()), ownsHttp: true)
    {
    }

    /// <summary>
    /// Creates a client that uses the supplied <paramref name="httpClient"/> (not disposed by
    /// this client). Use this overload with <c>IHttpClientFactory</c>, custom message
    /// handlers, or a mocked handler in tests.
    /// </summary>
    public OabpClient(HttpClient httpClient, OabpClientOptions? options = null)
        : this(options ?? new OabpClientOptions(), httpClient ?? throw new ArgumentNullException(nameof(httpClient)), ownsHttp: false)
    {
    }

    private OabpClient(OabpClientOptions options, HttpClient httpClient, bool ownsHttp)
    {
        _options = options;
        _http = httpClient;
        _ownsHttp = ownsHttp;

        string raw = string.IsNullOrWhiteSpace(options.BaseUrl)
            ? OabpClientOptions.DefaultBaseUrl
            : options.BaseUrl.TrimEnd('/');
        if (!Uri.TryCreate(raw + "/", UriKind.Absolute, out Uri? baseUri))
        {
            throw new ArgumentException($"Invalid BaseUrl: '{options.BaseUrl}'.", nameof(options));
        }
        _baseUri = baseUri;
    }

    private static HttpClient CreateDefaultHttpClient(OabpClientOptions options)
        => new() { Timeout = options.Timeout };

    /// <summary>
    /// Lists the currently open missions. <c>GET /api/missions</c>.
    /// </summary>
    public async Task<IReadOnlyList<Mission>> ListMissionsAsync(CancellationToken cancellationToken = default)
    {
        List<Mission>? missions = await SendAsync<List<Mission>>(
            HttpMethod.Get, "/api/missions", body: null, cancellationToken).ConfigureAwait(false);
        return missions ?? new List<Mission>();
    }

    /// <summary>
    /// Returns the full detail (including submissions and resolution) for a single mission.
    /// <c>GET /api/missions/{id}</c>. A missing mission throws an <see cref="OabpApiException"/>
    /// whose <see cref="OabpApiException.IsNotFound"/> is <c>true</c>.
    /// </summary>
    public async Task<Mission> GetMissionAsync(string id, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrEmpty(id))
        {
            throw new ArgumentException("Mission id is required.", nameof(id));
        }
        string path = "/api/missions/" + Uri.EscapeDataString(id);
        Mission? m = await SendAsync<Mission>(HttpMethod.Get, path, body: null, cancellationToken).ConfigureAwait(false);
        return m ?? throw new OabpApiException(HttpStatusCode.NoContent, "GET", path, "empty body");
    }

    /// <summary>
    /// Posts a new bounty and returns the created mission as echoed by the server.
    /// <c>POST /api/missions</c>.
    /// </summary>
    /// <remarks>
    /// If <see cref="CreateMissionRequest.CreatorAgentId"/> is blank and the client was built
    /// with an <see cref="OabpClientOptions.AgentId"/>, that identity is used. The request is
    /// validated locally before any network call, so obvious mistakes fail fast.
    /// </remarks>
    public async Task<Mission> CreateMissionAsync(CreateMissionRequest request, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);
        if (string.IsNullOrEmpty(request.CreatorAgentId) && !string.IsNullOrEmpty(_options.AgentId))
        {
            request = request with { CreatorAgentId = _options.AgentId };
        }
        Validate(request);

        Mission? m = await SendAsync<Mission>(HttpMethod.Post, "/api/missions", request, cancellationToken).ConfigureAwait(false);
        return m ?? throw new OabpApiException(HttpStatusCode.NoContent, "POST", "/api/missions", "empty body");
    }

    /// <summary>
    /// Posts a deliverable (proof) against a mission. <c>POST /missions/{id}/submit</c>.
    /// </summary>
    /// <remarks>
    /// <para>
    /// The proof is free text or a URL; for <c>first_valid_match</c> it is matched against the
    /// mission's regex, and for <c>oracle</c> missions it is the artifact the oracle inspects.
    /// </para>
    /// <para>
    /// If <see cref="SubmitRequest.SubmitterAgentId"/> is blank and the client was built with an
    /// <see cref="OabpClientOptions.AgentId"/>, that identity is used.
    /// </para>
    /// <para>
    /// Note: this endpoint has <b>no</b> <c>/api</c> prefix — it is
    /// <c>POST /missions/{id}/submit</c>. The SDK handles this for you.
    /// </para>
    /// </remarks>
    public async Task<SubmitResult> SubmitAsync(string missionId, SubmitRequest request, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrEmpty(missionId))
        {
            throw new ArgumentException("Mission id is required.", nameof(missionId));
        }
        ArgumentNullException.ThrowIfNull(request);

        if (string.IsNullOrEmpty(request.SubmitterAgentId) && !string.IsNullOrEmpty(_options.AgentId))
        {
            request = request with { SubmitterAgentId = _options.AgentId };
        }
        if (string.IsNullOrEmpty(request.SubmitterAgentId))
        {
            throw new ArgumentException(
                "submitter_agent_id is required (set it on the request or via OabpClientOptions.AgentId).",
                nameof(request));
        }
        if (string.IsNullOrEmpty(request.Proof))
        {
            throw new ArgumentException("proof is required.", nameof(request));
        }

        string path = "/missions/" + Uri.EscapeDataString(missionId) + "/submit";
        SubmitResult? res = await SendAsync<SubmitResult>(HttpMethod.Post, path, request, cancellationToken).ConfigureAwait(false);
        return res ?? new SubmitResult { Accepted = false };
    }

    /// <summary>Returns protocol-wide counters. <c>GET /api/stats</c>.</summary>
    public async Task<Stats> GetStatsAsync(CancellationToken cancellationToken = default)
    {
        Stats? s = await SendAsync<Stats>(HttpMethod.Get, "/api/stats", body: null, cancellationToken).ConfigureAwait(false);
        return s ?? new Stats();
    }

    /// <summary>
    /// Returns an agent's standing in the AIGEN points ledger.
    /// <c>GET /api/reputation/{agent_id}</c>. If <paramref name="agentId"/> is blank, the
    /// client's configured <see cref="OabpClientOptions.AgentId"/> is used.
    /// </summary>
    public async Task<Reputation> GetReputationAsync(string? agentId = null, CancellationToken cancellationToken = default)
    {
        string? id = string.IsNullOrEmpty(agentId) ? _options.AgentId : agentId;
        if (string.IsNullOrEmpty(id))
        {
            throw new ArgumentException(
                "Agent id is required (pass it or set OabpClientOptions.AgentId).", nameof(agentId));
        }
        string path = "/api/reputation/" + Uri.EscapeDataString(id);
        Reputation? rep = await SendAsync<Reputation>(HttpMethod.Get, path, body: null, cancellationToken).ConfigureAwait(false);
        rep ??= new Reputation();
        return string.IsNullOrEmpty(rep.AgentId) ? rep with { AgentId = id } : rep;
    }

    // --- HTTP plumbing -------------------------------------------------------

    /// <summary>
    /// Core request helper: builds the request (optionally with a JSON body), sends it, maps
    /// non-2xx responses to <see cref="OabpApiException"/>, and deserializes the JSON body into
    /// <typeparamref name="T"/> (or <c>default</c> for an empty body).
    /// </summary>
    private async Task<T?> SendAsync<T>(HttpMethod method, string path, object? body, CancellationToken cancellationToken)
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
            string json = JsonSerializer.Serialize(body, body.GetType(), JsonDefaults.Options);
            request.Content = new StringContent(json, Encoding.UTF8, "application/json");
        }

        HttpResponseMessage response;
        try
        {
            response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken)
                .ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw; // surface cancellation/timeout unchanged
        }
        catch (HttpRequestException ex)
        {
            throw new OabpTransportException($"oabp: {method} {path}: {ex.Message}", ex);
        }

        using (response)
        {
            string content = await ReadBodyAsync(response, cancellationToken).ConfigureAwait(false);

            if (!response.IsSuccessStatusCode)
            {
                throw new OabpApiException(response.StatusCode, method.Method, path, content);
            }
            if (string.IsNullOrWhiteSpace(content))
            {
                return default;
            }
            try
            {
                return JsonSerializer.Deserialize<T>(content, JsonDefaults.Options);
            }
            catch (JsonException ex)
            {
                throw new OabpTransportException($"oabp: {method} {path}: decode response: {ex.Message}", ex);
            }
        }
    }

    private static async Task<string> ReadBodyAsync(HttpResponseMessage response, CancellationToken ct)
    {
#if NET8_0_OR_GREATER
        return await response.Content.ReadAsStringAsync(ct).ConfigureAwait(false);
#else
        return await response.Content.ReadAsStringAsync().ConfigureAwait(false);
#endif
    }

    /// <summary>Joins a path onto the base URL, passing absolute URLs through unchanged.</summary>
    private Uri ResolveUri(string path)
    {
        if (path.StartsWith("http://", StringComparison.OrdinalIgnoreCase) ||
            path.StartsWith("https://", StringComparison.OrdinalIgnoreCase))
        {
            return new Uri(path, UriKind.Absolute);
        }
        // _baseUri ends with '/'; strip the leading '/' so the path is treated as relative.
        return new Uri(_baseUri, path.TrimStart('/'));
    }

    private static void Validate(CreateMissionRequest r)
    {
        if (string.IsNullOrEmpty(r.CreatorAgentId))
        {
            throw new ArgumentException("creator_agent_id is required (set it or use OabpClientOptions.AgentId).");
        }
        if (string.IsNullOrEmpty(r.Title))
        {
            throw new ArgumentException("title is required.");
        }
        if (r.RewardAmount <= 0)
        {
            throw new ArgumentException($"reward_amount must be > 0, got {r.RewardAmount}.");
        }
        if (r.RewardCurrency is null || string.IsNullOrEmpty(r.RewardCurrency.Value))
        {
            throw new ArgumentException("reward_currency is required (AIGEN or USDC).");
        }
        if (r.VerificationType is null || string.IsNullOrEmpty(r.VerificationType.Value))
        {
            throw new ArgumentException("verification_type is required.");
        }
        if (r.DeadlineHours <= 0)
        {
            throw new ArgumentException($"deadline_hours must be > 0, got {r.DeadlineHours}.");
        }
        if (r.VerificationType == VerificationType.FirstValidMatch && string.IsNullOrEmpty(r.VerificationParams.Regex))
        {
            throw new ArgumentException("first_valid_match requires verification_params.regex.");
        }
    }

    /// <inheritdoc/>
    public void Dispose()
    {
        if (_ownsHttp)
        {
            _http.Dispose();
        }
    }
}

/// <summary>
/// Thrown when a request cannot complete at the transport/serialization layer (DNS, TLS,
/// connection reset, or an undecodable body) — as opposed to a well-formed non-2xx HTTP
/// response, which is an <see cref="OabpApiException"/>.
/// </summary>
public sealed class OabpTransportException : OabpException
{
    internal OabpTransportException(string message, Exception inner) : base(message, inner) { }
}
