using System.Net;
using System.Text.Json;

namespace Oabp.Client;

/// <summary>
/// Base type for every exception raised by this SDK.
/// </summary>
public abstract class OabpException : Exception
{
    /// <summary>Creates an <see cref="OabpException"/>.</summary>
    protected OabpException(string message, Exception? inner = null) : base(message, inner) { }
}

/// <summary>
/// Thrown for non-2xx HTTP responses. Exposes the status code, the request that failed,
/// the raw response body, and any decoded JSON error message.
/// </summary>
public sealed class OabpApiException : OabpException
{
    /// <summary>The HTTP status code returned by the server.</summary>
    public HttpStatusCode StatusCode { get; }

    /// <summary>The HTTP method of the failed request (e.g. <c>GET</c>).</summary>
    public string Method { get; }

    /// <summary>The request path that failed.</summary>
    public string Path { get; }

    /// <summary>The raw response body, verbatim.</summary>
    public string Body { get; }

    /// <summary>
    /// The <c>error</c>/<c>message</c>/<c>detail</c> field decoded from a JSON error body,
    /// when present; otherwise <c>null</c>.
    /// </summary>
    public string? ResponseMessage { get; }

    /// <summary>True when <see cref="StatusCode"/> is 404 Not Found.</summary>
    public bool IsNotFound => StatusCode == HttpStatusCode.NotFound;

    internal OabpApiException(HttpStatusCode statusCode, string method, string path, string body)
        : base(BuildMessage(statusCode, method, path, body, out string? decoded))
    {
        StatusCode = statusCode;
        Method = method;
        Path = path;
        Body = body;
        ResponseMessage = decoded;
    }

    private static string BuildMessage(
        HttpStatusCode statusCode, string method, string path, string body, out string? decoded)
    {
        decoded = TryDecodeError(body);
        string detail = decoded ?? body.Trim();
        if (detail.Length > 300)
        {
            detail = detail[..300] + "…";
        }
        return detail.Length == 0
            ? $"oabp: {method} {path}: {(int)statusCode} {statusCode}"
            : $"oabp: {method} {path}: {(int)statusCode} {statusCode}: {detail}";
    }

    /// <summary>Best-effort extraction of a JSON error message from a response body.</summary>
    private static string? TryDecodeError(string body)
    {
        if (string.IsNullOrWhiteSpace(body))
        {
            return null;
        }
        try
        {
            using JsonDocument doc = JsonDocument.Parse(body);
            if (doc.RootElement.ValueKind != JsonValueKind.Object)
            {
                return null;
            }
            foreach (string key in new[] { "error", "message", "detail" })
            {
                if (doc.RootElement.TryGetProperty(key, out JsonElement el) &&
                    el.ValueKind == JsonValueKind.String)
                {
                    string? s = el.GetString();
                    if (!string.IsNullOrEmpty(s))
                    {
                        return s;
                    }
                }
            }
        }
        catch (JsonException)
        {
            // Non-JSON body: fall through to null and let the raw body be shown.
        }
        return null;
    }
}

/// <summary>
/// Thrown when the A2A JSON-RPC endpoint returns an <c>error</c> object.
/// </summary>
public sealed class OabpRpcException : OabpException
{
    /// <summary>The JSON-RPC error code (e.g. <c>-32601</c> for "method not found").</summary>
    public int Code { get; }

    /// <summary>The JSON-RPC error message.</summary>
    public string RpcMessage { get; }

    /// <summary>Optional structured error data, as raw JSON, when present.</summary>
    public string? ErrorData { get; }

    internal OabpRpcException(int code, string message, string? data)
        : base(data is null
            ? $"oabp a2a: rpc error {code}: {message}"
            : $"oabp a2a: rpc error {code}: {message}: {data}")
    {
        Code = code;
        RpcMessage = message;
        ErrorData = data;
    }
}
