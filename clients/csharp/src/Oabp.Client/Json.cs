using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.Json.Serialization;

namespace Oabp.Client;

/// <summary>
/// Marker for the "open enum" value records (<see cref="Currency"/>, <see cref="VerificationType"/>,
/// <see cref="MissionStatus"/>): a small set of named constants that nonetheless preserve
/// any unknown wire value rather than failing to deserialize.
/// </summary>
/// <typeparam name="T">The implementing record type.</typeparam>
public interface IStringEnumLike<out T>
{
    /// <summary>The raw wire string.</summary>
    string Value { get; }

    /// <summary>Constructs an instance from an arbitrary wire string.</summary>
    static abstract T Of(string value);
}

/// <summary>
/// Serializes an <see cref="IStringEnumLike{T}"/> as its raw string and deserializes any
/// JSON string back into it, so unknown protocol values round-trip losslessly.
/// </summary>
/// <typeparam name="T">An <see cref="IStringEnumLike{T}"/> record.</typeparam>
public sealed class StringEnumLikeConverter<T> : JsonConverter<T>
    where T : IStringEnumLike<T>
{
    /// <inheritdoc/>
    public override T? Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        if (reader.TokenType == JsonTokenType.Null)
        {
            return default;
        }
        if (reader.TokenType != JsonTokenType.String)
        {
            throw new JsonException($"Expected string for {typeToConvert.Name}, got {reader.TokenType}.");
        }
        return T.Of(reader.GetString()!);
    }

    /// <inheritdoc/>
    public override void Write(Utf8JsonWriter writer, T value, JsonSerializerOptions options)
        => writer.WriteStringValue(value.Value);
}

/// <summary>
/// Converts a unix-seconds timestamp to/from <see cref="DateTimeOffset"/>.
/// </summary>
/// <remarks>
/// The protocol emits deadlines and timestamps as unix seconds. This converter accepts a
/// JSON number (integer or fractional) or a numeric string, tolerating the variation seen
/// across deployments. <c>null</c> decodes to <c>null</c>. On write it emits an integer
/// number of seconds.
/// </remarks>
public sealed class UnixTimeConverter : JsonConverter<DateTimeOffset?>
{
    /// <inheritdoc/>
    public override DateTimeOffset? Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        switch (reader.TokenType)
        {
            case JsonTokenType.Null:
                return null;

            case JsonTokenType.Number:
                // Read as double to tolerate fractional seconds, then convert to ticks.
                double seconds = reader.GetDouble();
                return FromUnixSeconds(seconds);

            case JsonTokenType.String:
                string raw = reader.GetString()!;
                if (string.IsNullOrWhiteSpace(raw))
                {
                    return null;
                }
                if (!double.TryParse(raw, System.Globalization.NumberStyles.Float,
                        System.Globalization.CultureInfo.InvariantCulture, out double parsed))
                {
                    throw new JsonException($"Cannot parse unix time from string \"{raw}\".");
                }
                return FromUnixSeconds(parsed);

            default:
                throw new JsonException($"Unexpected token {reader.TokenType} for unix time.");
        }
    }

    /// <inheritdoc/>
    public override void Write(Utf8JsonWriter writer, DateTimeOffset? value, JsonSerializerOptions options)
    {
        if (value is null)
        {
            writer.WriteNullValue();
            return;
        }
        writer.WriteNumberValue(value.Value.ToUnixTimeSeconds());
    }

    private static DateTimeOffset FromUnixSeconds(double seconds)
    {
        // DateTimeOffset.FromUnixTimeMilliseconds keeps sub-second precision; multiply
        // carefully to avoid losing the fractional part.
        long millis = (long)Math.Round(seconds * 1000.0, MidpointRounding.AwayFromZero);
        return DateTimeOffset.FromUnixTimeMilliseconds(millis);
    }
}

/// <summary>
/// Deserializes a <see cref="Submission"/> while retaining the complete raw JSON object in
/// <see cref="Submission.Extra"/>, so undocumented server fields are never dropped.
/// </summary>
public sealed class SubmissionConverter : JsonConverter<Submission>
{
    /// <inheritdoc/>
    public override Submission Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        JsonObject? node = JsonNode.Parse(ref reader) as JsonObject
            ?? throw new JsonException("Expected a JSON object for Submission.");

        return new Submission
        {
            Id = GetString(node, "id"),
            SubmitterAgentId = GetString(node, "submitter_agent_id"),
            Proof = GetString(node, "proof"),
            Verified = node.TryGetPropertyValue("verified", out JsonNode? v) && v is not null ? v.GetValue<bool>() : null,
            CreatedAt = ReadUnix(node, "created_at"),
            Extra = node,
        };
    }

    /// <inheritdoc/>
    public override void Write(Utf8JsonWriter writer, Submission value, JsonSerializerOptions options)
    {
        // Use the default property contract for writing (Extra is [JsonIgnore]).
        var clone = new SubmissionDto
        {
            Id = value.Id,
            SubmitterAgentId = value.SubmitterAgentId,
            Proof = value.Proof,
            Verified = value.Verified,
            CreatedAt = value.CreatedAt,
        };
        JsonSerializer.Serialize(writer, clone, options);
    }

    internal static string? GetString(JsonObject node, string key)
        => node.TryGetPropertyValue(key, out JsonNode? n) && n is not null ? n.GetValue<string>() : null;

    internal static DateTimeOffset? ReadUnix(JsonObject node, string key)
    {
        if (!node.TryGetPropertyValue(key, out JsonNode? n) || n is null)
        {
            return null;
        }
        // JsonValue can hold a number or a string; let the dedicated converter handle both.
        var conv = new UnixTimeConverter();
        byte[] bytes = System.Text.Encoding.UTF8.GetBytes(n.ToJsonString());
        var r = new Utf8JsonReader(bytes);
        r.Read();
        return conv.Read(ref r, typeof(DateTimeOffset?), JsonDefaults.Options);
    }

    // Plain DTO mirroring the writable fields, used only for serialization output.
    private sealed record SubmissionDto
    {
        [JsonPropertyName("id")] public string? Id { get; init; }
        [JsonPropertyName("submitter_agent_id")] public string? SubmitterAgentId { get; init; }
        [JsonPropertyName("proof")] public string? Proof { get; init; }
        [JsonPropertyName("verified")] public bool? Verified { get; init; }

        [JsonPropertyName("created_at")]
        [JsonConverter(typeof(UnixTimeConverter))]
        public DateTimeOffset? CreatedAt { get; init; }
    }
}

/// <summary>
/// Deserializes a <see cref="Reputation"/> while retaining the complete raw JSON object in
/// <see cref="Reputation.Extra"/>.
/// </summary>
public sealed class ReputationConverter : JsonConverter<Reputation>
{
    /// <inheritdoc/>
    public override Reputation Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        JsonObject node = JsonNode.Parse(ref reader) as JsonObject
            ?? throw new JsonException("Expected a JSON object for Reputation.");

        return new Reputation
        {
            AgentId = SubmissionConverter.GetString(node, "agent_id") ?? "",
            AigenBalance = GetDouble(node, "aigen_balance") ?? 0,
            UsdcEarned = GetDouble(node, "usdc_earned"),
            MissionsWon = (int)(GetDouble(node, "missions_won") ?? 0),
            MissionsPosted = GetInt(node, "missions_posted"),
            Submissions = GetInt(node, "submissions"),
            Rank = GetInt(node, "rank"),
            Extra = node,
        };
    }

    /// <inheritdoc/>
    public override void Write(Utf8JsonWriter writer, Reputation value, JsonSerializerOptions options)
    {
        writer.WriteStartObject();
        writer.WriteString("agent_id", value.AgentId);
        writer.WriteNumber("aigen_balance", value.AigenBalance);
        if (value.UsdcEarned is { } u) writer.WriteNumber("usdc_earned", u);
        writer.WriteNumber("missions_won", value.MissionsWon);
        if (value.MissionsPosted is { } mp) writer.WriteNumber("missions_posted", mp);
        if (value.Submissions is { } s) writer.WriteNumber("submissions", s);
        if (value.Rank is { } r) writer.WriteNumber("rank", r);
        writer.WriteEndObject();
    }

    private static double? GetDouble(JsonObject node, string key)
        => node.TryGetPropertyValue(key, out JsonNode? n) && n is not null ? n.GetValue<double>() : null;

    private static int? GetInt(JsonObject node, string key)
        => node.TryGetPropertyValue(key, out JsonNode? n) && n is not null ? (int)n.GetValue<double>() : null;
}

/// <summary>Shared <see cref="JsonSerializerOptions"/> for the SDK.</summary>
public static class JsonDefaults
{
    /// <summary>
    /// The serializer options used for every request/response: explicit
    /// <c>JsonPropertyName</c> tags (so no naming policy is needed), nulls omitted on write,
    /// and the SDK's custom converters registered.
    /// </summary>
    public static JsonSerializerOptions Options { get; } = Build();

    private static JsonSerializerOptions Build()
    {
        var o = new JsonSerializerOptions
        {
            DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
            PropertyNameCaseInsensitive = true,
            NumberHandling = JsonNumberHandling.AllowReadingFromString,
        };
        o.Converters.Add(new SubmissionConverter());
        o.Converters.Add(new ReputationConverter());
        // Note: StringEnumLikeConverter<T> and UnixTimeConverter are applied via
        // [JsonConverter] attributes on the types/properties, so they need not be listed here.
        return o;
    }
}
