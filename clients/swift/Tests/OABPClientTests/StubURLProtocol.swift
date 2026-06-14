//
//  StubURLProtocol.swift
//  OABPClientTests
//
//  A `URLProtocol` subclass that intercepts every request made through a
//  `URLSession` configured with it, and lets a test install a closure that maps
//  the outgoing `URLRequest` to a canned `(HTTPURLResponse, Data)`.
//
//  This is the standard, network-free way to test a URLSession-based SDK and is
//  what the acceptance criterion ("XCTest with URLProtocol stub passes") asks for.
//

import Foundation

#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

final class StubURLProtocol: URLProtocol {

    /// What a stub returns: either an HTTP response + body, or a transport error.
    enum Outcome {
        case response(statusCode: Int, headers: [String: String], body: Data)
        case failure(Error)
    }

    /// A captured request together with the body bytes (URLProtocol strips
    /// `httpBody` for streamed bodies, so we reconstruct it from `httpBodyStream`).
    struct CapturedRequest {
        let request: URLRequest
        let body: Data?
    }

    // Thread-safe handler storage. URLProtocol callbacks run off the test thread.
    private static let lock = NSLock()
    private static var _handler: ((URLRequest) throws -> Outcome)?
    private static var _captured: [CapturedRequest] = []

    static func setHandler(_ handler: @escaping (URLRequest) throws -> Outcome) {
        lock.lock(); defer { lock.unlock() }
        _handler = handler
        _captured = []
    }

    static func reset() {
        lock.lock(); defer { lock.unlock() }
        _handler = nil
        _captured = []
    }

    static var capturedRequests: [CapturedRequest] {
        lock.lock(); defer { lock.unlock() }
        return _captured
    }

    private static func handler() -> ((URLRequest) throws -> Outcome)? {
        lock.lock(); defer { lock.unlock() }
        return _handler
    }

    private static func capture(_ captured: CapturedRequest) {
        lock.lock(); defer { lock.unlock() }
        _captured.append(captured)
    }

    /// Build a `URLSession` wired to this stub.
    static func makeSession() -> URLSession {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [StubURLProtocol.self]
        return URLSession(configuration: config)
    }

    // MARK: URLProtocol

    override class func canInit(with request: URLRequest) -> Bool { true }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        // Reconstruct the request body (httpBody is often nil once URLSession
        // converts it to a stream).
        let body = Self.extractBody(from: request)
        Self.capture(CapturedRequest(request: request, body: body))

        guard let handler = Self.handler() else {
            let err = NSError(
                domain: "StubURLProtocol",
                code: -1,
                userInfo: [NSLocalizedDescriptionKey: "No stub handler installed"]
            )
            client?.urlProtocol(self, didFailWithError: err)
            return
        }

        do {
            switch try handler(request) {
            case let .response(statusCode, headers, data):
                let url = request.url ?? URL(string: "https://invalid.invalid")!
                let response = HTTPURLResponse(
                    url: url,
                    statusCode: statusCode,
                    httpVersion: "HTTP/1.1",
                    headerFields: headers
                )!
                client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
                client?.urlProtocol(self, didLoad: data)
                client?.urlProtocolDidFinishLoading(self)
            case let .failure(error):
                client?.urlProtocol(self, didFailWithError: error)
            }
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() { /* no-op */ }

    // MARK: Helpers

    private static func extractBody(from request: URLRequest) -> Data? {
        if let body = request.httpBody {
            return body
        }
        guard let stream = request.httpBodyStream else { return nil }
        stream.open()
        defer { stream.close() }
        var data = Data()
        let bufferSize = 4096
        let buffer = UnsafeMutablePointer<UInt8>.allocate(capacity: bufferSize)
        defer { buffer.deallocate() }
        while stream.hasBytesAvailable {
            let read = stream.read(buffer, maxLength: bufferSize)
            if read <= 0 { break }
            data.append(buffer, count: read)
        }
        return data
    }
}
