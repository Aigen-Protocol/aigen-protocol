package org.aigen.oabp;

/**
 * Checked exception for every failure surfaced by {@link OabpClient}.
 *
 * <p>One checked type covers the three failure families a caller must handle:
 * <ul>
 *   <li><b>transport</b> — the request never produced an HTTP response (I/O error,
 *       connection refused, timeout, interruption);</li>
 *   <li><b>protocol</b> — a response arrived but could not be parsed or was malformed;</li>
 *   <li><b>API</b> — the server returned a non-2xx status (see {@link ApiException},
 *       which exposes the status code and raw body).</li>
 * </ul>
 *
 * <p>It is checked deliberately: talking to a remote service can always fail, and the
 * SDK forces callers to acknowledge that at compile time rather than discover it at
 * runtime.
 */
public class OabpException extends Exception {

    private static final long serialVersionUID = 1L;

    public OabpException(String message) {
        super(message);
    }

    public OabpException(String message, Throwable cause) {
        super(message, cause);
    }

    /**
     * Thrown when the OABP server returns a non-2xx HTTP status.
     *
     * <p>Carries the {@link #statusCode()} and the raw response {@link #body()} so callers
     * can branch on, log, or surface the server's error detail.
     */
    public static class ApiException extends OabpException {

        private static final long serialVersionUID = 1L;

        private final int statusCode;
        private final transient String body;

        public ApiException(int statusCode, String body, String message) {
            super(message);
            this.statusCode = statusCode;
            this.body = body;
        }

        /** @return the HTTP status code returned by the server. */
        public int statusCode() {
            return statusCode;
        }

        /** @return the raw response body (possibly empty, never {@code null}). */
        public String body() {
            return body == null ? "" : body;
        }

        /** @return {@code true} for 4xx statuses (the request was at fault). */
        public boolean isClientError() {
            return statusCode >= 400 && statusCode < 500;
        }

        /** @return {@code true} for 5xx statuses (the server failed). */
        public boolean isServerError() {
            return statusCode >= 500 && statusCode < 600;
        }

        /** @return {@code true} if the resource was not found (HTTP 404). */
        public boolean isNotFound() {
            return statusCode == 404;
        }
    }
}
