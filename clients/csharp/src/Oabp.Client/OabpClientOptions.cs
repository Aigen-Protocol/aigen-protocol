namespace Oabp.Client;

/// <summary>
/// Configuration for an <see cref="OabpClient"/>.
/// </summary>
public sealed record OabpClientOptions
{
    /// <summary>The public OABP / AIGEN deployment.</summary>
    public const string DefaultBaseUrl = "https://cryptogenesis.duckdns.org";

    /// <summary>Default <c>User-Agent</c> sent with every request.</summary>
    public const string DefaultUserAgent = "oabp-dotnet/0.1";

    /// <summary>
    /// API base URL. Defaults to <see cref="DefaultBaseUrl"/>. A trailing slash is trimmed.
    /// </summary>
    public string BaseUrl { get; init; } = DefaultBaseUrl;

    /// <summary>
    /// The calling agent's identity. When set, it is used as the default
    /// <c>creator_agent_id</c>/<c>submitter_agent_id</c> wherever the caller leaves those
    /// fields blank, so agents need not repeat their id on every call.
    /// </summary>
    public string? AgentId { get; init; }

    /// <summary>
    /// Optional bearer token, attached as <c>Authorization: Bearer …</c> on every request.
    /// The public deployment is permissionless, but private deployments may gate writes.
    /// </summary>
    public string? ApiKey { get; init; }

    /// <summary>The <c>User-Agent</c> header value. Defaults to <see cref="DefaultUserAgent"/>.</summary>
    public string UserAgent { get; init; } = DefaultUserAgent;

    /// <summary>
    /// Per-request timeout used only when the SDK creates its own <see cref="HttpClient"/>
    /// (i.e. when one is not supplied to the constructor). Defaults to 30 seconds.
    /// </summary>
    public TimeSpan Timeout { get; init; } = TimeSpan.FromSeconds(30);
}
