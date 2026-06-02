//
//  HTTPTransport.swift
//  OABPClient
//
//  A thin async wrapper over `URLSession` that performs requests, maps failures
//  to `OabpError`, and decodes JSON. Kept separate from `OabpClient` so the
//  networking concern is isolated and unit-testable (inject a `URLSession` whose
//  configuration carries a `URLProtocol` stub).
//

import Foundation

#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// Internal HTTP method enum.
enum HTTPMethod: String, Sendable {
    case get = "GET"
    case post = "POST"
}

/// Performs JSON HTTP requests for the SDK.
///
/// Held exclusively inside the `OabpClient` actor, which provides isolation, so
/// it does not declare its own `Sendable` conformance (which would raise the
/// question of `URLSession`'s sendability under strict concurrency). All stored
/// values are immutable; `URLSession` is internally thread-safe.
struct HTTPTransport {
    let baseURL: URL
    let session: URLSession
    /// Extra headers applied to every request (e.g. an `Authorization` bearer).
    let defaultHeaders: [String: String]
    let timeout: TimeInterval

    init(
        baseURL: URL,
        session: URLSession,
        defaultHeaders: [String: String],
        timeout: TimeInterval
    ) {
        self.baseURL = baseURL
        self.session = session
        self.defaultHeaders = defaultHeaders
        self.timeout = timeout
    }

    // A fresh decoder/encoder per call avoids shared mutable state across tasks.
    private func makeDecoder() -> JSONDecoder { JSONDecoder() }
    private func makeEncoder() -> JSONEncoder {
        let e = JSONEncoder()
        // Stable, human-readable bodies; key order is driven by CodingKeys anyway.
        e.outputFormatting = [.withoutEscapingSlashes]
        return e
    }

    /// Resolve a path (e.g. `/api/missions` or `api/missions/42`) against `baseURL`,
    /// appending query items if provided.
    ///
    /// Builds the absolute URL by string-joining `baseURL` and `path` (rather than
    /// `appendingPathComponent`, which can percent-encode multi-segment strings and
    /// behaves differently on Linux vs Apple). Path segments that need escaping are
    /// the caller's responsibility (e.g. mission ids are escaped in `OabpClient`).
    private func makeURL(path: String, query: [URLQueryItem]) throws -> URL {
        // Normalise the boundary between baseURL and path to exactly one slash.
        var base = baseURL.absoluteString
        while base.hasSuffix("/") { base.removeLast() }
        let suffix = path.hasPrefix("/") ? path : "/" + path
        let joined = base + suffix

        guard var components = URLComponents(string: joined) else {
            throw OabpError.invalidURL(joined)
        }
        if !query.isEmpty {
            components.queryItems = query
        }
        guard let url = components.url else {
            throw OabpError.invalidURL(joined)
        }
        return url
    }

    /// Perform a request and decode the JSON body into `Response`.
    ///
    /// - Parameters:
    ///   - method: HTTP verb.
    ///   - path: path relative to `baseURL`.
    ///   - query: query items (GET).
    ///   - body: an `Encodable` request body (POST); `nil` for none.
    /// - Returns: the decoded response.
    /// - Throws: ``OabpError`` for transport, HTTP, encoding or decoding failures.
    func request<Response: Decodable, Body: Encodable>(
        _ method: HTTPMethod,
        path: String,
        query: [URLQueryItem] = [],
        body: Body?
    ) async throws -> Response {
        let data = try await requestData(method, path: path, query: query, body: body)
        do {
            return try makeDecoder().decode(Response.self, from: data)
        } catch {
            let snippet = String(data: data, encoding: .utf8) ?? "<\(data.count) bytes>"
            throw OabpError.decoding(message: "\(error) — payload: \(snippet.prefixSnippet())")
        }
    }

    /// Perform a request and return the raw response body.
    func requestData<Body: Encodable>(
        _ method: HTTPMethod,
        path: String,
        query: [URLQueryItem] = [],
        body: Body?
    ) async throws -> Data {
        let url = try makeURL(path: path, query: query)
        var req = URLRequest(url: url, timeoutInterval: timeout)
        req.httpMethod = method.rawValue
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        for (k, v) in defaultHeaders {
            req.setValue(v, forHTTPHeaderField: k)
        }

        if let body = body {
            do {
                req.httpBody = try makeEncoder().encode(body)
            } catch {
                throw OabpError.encoding(message: "\(error)")
            }
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: req)
        } catch let error as OabpError {
            throw error
        } catch {
            throw OabpError.transport(message: "\(error.localizedDescription)")
        }

        guard let http = response as? HTTPURLResponse else {
            throw OabpError.transport(message: "Non-HTTP response")
        }

        guard (200..<300).contains(http.statusCode) else {
            let bodyText = String(data: data, encoding: .utf8) ?? ""
            throw OabpError.httpStatus(code: http.statusCode, body: bodyText)
        }

        return data
    }
}

private extension String {
    /// Truncate a payload snippet so error messages stay readable.
    func prefixSnippet(_ limit: Int = 500) -> String {
        if count <= limit { return self }
        return String(prefix(limit)) + "…"
    }
}

// MARK: - URLSession.data backport for Linux

#if canImport(FoundationNetworking)
extension URLSession {
    /// `data(for:)` is not available in some swift-corelibs-foundation versions
    /// (Linux). This continuation-based shim provides the same async surface so
    /// the SDK builds identically on Linux and Apple platforms.
    func data(for request: URLRequest) async throws -> (Data, URLResponse) {
        try await withCheckedThrowingContinuation { continuation in
            let task = self.dataTask(with: request) { data, response, error in
                if let error = error {
                    continuation.resume(throwing: error)
                    return
                }
                guard let data = data, let response = response else {
                    continuation.resume(
                        throwing: OabpError.transport(message: "Empty response")
                    )
                    return
                }
                continuation.resume(returning: (data, response))
            }
            task.resume()
        }
    }
}
#endif
