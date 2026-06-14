package org.aigen.oabp

/**
 * Base type for every failure surfaced by [OabpClient].
 *
 * Three failure families a caller must handle:
 *  - **transport** — the request never produced an HTTP response (I/O error, connection
 *    refused, timeout): [OabpTransportException];
 *  - **protocol** — a response arrived but could not be parsed / was malformed:
 *    [OabpSerializationException];
 *  - **API** — the server returned a non-2xx status: [OabpApiException], which exposes the
 *    status code and raw body.
 *
 * Unlike the Java SDK these are unchecked (Kotlin has no checked exceptions); suspend
 * functions document the failure modes they throw.
 */
public sealed class OabpException(
    message: String,
    cause: Throwable? = null,
) : RuntimeException(message, cause)

/** The request never produced an HTTP response (I/O error, connection refused, timeout). */
public class OabpTransportException(
    message: String,
    cause: Throwable? = null,
) : OabpException(message, cause)

/** A response arrived but could not be (de)serialized into the expected shape. */
public class OabpSerializationException(
    message: String,
    cause: Throwable? = null,
) : OabpException(message, cause)

/**
 * The OABP server returned a non-2xx HTTP status.
 *
 * @property statusCode the HTTP status code returned by the server.
 * @property body the raw response body (possibly empty, never `null`).
 */
public class OabpApiException(
    public val statusCode: Int,
    public val body: String,
    message: String,
) : OabpException(message) {
    /** `true` for 4xx statuses (the request was at fault). */
    public val isClientError: Boolean
        get() = statusCode in 400..499

    /** `true` for 5xx statuses (the server failed). */
    public val isServerError: Boolean
        get() = statusCode in 500..599

    /** `true` if the resource was not found (HTTP 404). */
    public val isNotFound: Boolean
        get() = statusCode == 404
}
