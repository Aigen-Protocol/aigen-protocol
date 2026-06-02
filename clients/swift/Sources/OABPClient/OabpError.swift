//
//  OabpError.swift
//  OABPClient
//
//  The single error type thrown by every `OabpClient` call.
//

import Foundation

/// Errors surfaced by ``OabpClient``.
///
/// Conforms to `LocalizedError` so `error.localizedDescription` is meaningful,
/// and is `Sendable` so it can be thrown across actor boundaries.
public enum OabpError: Error, Sendable {
    /// The configured base URL or a derived endpoint URL was invalid.
    case invalidURL(String)

    /// The underlying `URLSession` request failed (no connectivity, timeout,
    /// TLS failure, …). Carries a message extracted from the wrapped error.
    case transport(message: String)

    /// The server returned a non-2xx status. `body` is the (possibly empty)
    /// response payload as UTF-8 text, useful for surfacing API error messages.
    case httpStatus(code: Int, body: String)

    /// The response could not be decoded into the expected type.
    case decoding(message: String)

    /// The response could not be encoded for sending.
    case encoding(message: String)

    /// The server returned 2xx but the payload was semantically invalid
    /// (e.g. an `{"error": ...}` envelope, or a missing required field).
    case api(message: String)
}

extension OabpError: LocalizedError {
    public var errorDescription: String? {
        switch self {
        case .invalidURL(let s):
            return "Invalid URL: \(s)"
        case .transport(let message):
            return "Network error: \(message)"
        case .httpStatus(let code, let body):
            let trimmed = body.trimmingCharacters(in: .whitespacesAndNewlines)
            if trimmed.isEmpty {
                return "HTTP \(code)"
            }
            return "HTTP \(code): \(trimmed)"
        case .decoding(let message):
            return "Failed to decode response: \(message)"
        case .encoding(let message):
            return "Failed to encode request: \(message)"
        case .api(let message):
            return "API error: \(message)"
        }
    }
}

extension OabpError: Equatable {
    public static func == (lhs: OabpError, rhs: OabpError) -> Bool {
        switch (lhs, rhs) {
        case let (.invalidURL(a), .invalidURL(b)):
            return a == b
        case let (.transport(a), .transport(b)):
            return a == b
        case let (.httpStatus(ac, ab), .httpStatus(bc, bb)):
            return ac == bc && ab == bb
        case let (.decoding(a), .decoding(b)):
            return a == b
        case let (.encoding(a), .encoding(b)):
            return a == b
        case let (.api(a), .api(b)):
            return a == b
        default:
            return false
        }
    }
}
