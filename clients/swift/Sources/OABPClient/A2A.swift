//
//  A2A.swift
//  OABPClient
//
//  Agent-to-Agent (A2A) JSON-RPC 2.0 types for `POST /api/a2a`, plus the
//  Agent Card / JWKS discovery models.
//
//  The A2A surface is intentionally schema-light here: JSON-RPC `params` and
//  `result` are modelled as a small dynamic `JSONValue` so the SDK can speak the
//  three documented methods (`message/send`, `tasks/get`, `tasks/list`) without
//  pinning the server's evolving task schema. Strongly-typed convenience wrappers
//  live in `OabpClient`.
//

import Foundation

// MARK: - JSON-RPC envelope

/// A JSON-RPC 2.0 request envelope.
public struct JSONRPCRequest: Codable, Sendable {
    public let jsonrpc: String
    public let id: String
    public let method: String
    public let params: JSONValue?

    public init(id: String = UUID().uuidString, method: String, params: JSONValue? = nil) {
        self.jsonrpc = "2.0"
        self.id = id
        self.method = method
        self.params = params
    }
}

/// A JSON-RPC 2.0 error object.
public struct JSONRPCError: Codable, Sendable, Hashable, Error {
    public let code: Int
    public let message: String
    public let data: JSONValue?

    public init(code: Int, message: String, data: JSONValue? = nil) {
        self.code = code
        self.message = message
        self.data = data
    }
}

/// A JSON-RPC 2.0 response envelope. Exactly one of `result` / `error` is set.
public struct JSONRPCResponse: Codable, Sendable {
    public let jsonrpc: String
    public let id: JSONValue?
    public let result: JSONValue?
    public let error: JSONRPCError?

    public init(id: JSONValue?, result: JSONValue?, error: JSONRPCError?) {
        self.jsonrpc = "2.0"
        self.id = id
        self.result = result
        self.error = error
    }
}

// MARK: - Agent Card

/// The discovery document served at `/.well-known/agent-card.json` (ES256-signed).
///
/// Only a useful subset of the A2A Agent Card spec is modelled; unknown fields
/// are ignored on decode. `signature` / `signatures` (the JWS) and the JWKS URL
/// are surfaced so callers can verify provenance out-of-band.
public struct AgentCard: Codable, Sendable, Hashable {
    public var name: String?
    public var description: String?
    public var url: String?
    public var version: String?
    public var documentationUrl: String?
    public var capabilities: [String: JSONValue]?
    public var skills: [JSONValue]?
    /// Detached/embedded JWS signature(s), if the server attaches them in-body.
    public var signatures: [JSONValue]?

    enum CodingKeys: String, CodingKey {
        case name
        case description
        case url
        case version
        case documentationUrl = "documentationUrl"
        case capabilities
        case skills
        case signatures
    }
}

/// A single JSON Web Key, as found in `/.well-known/jwks.json`.
public struct JSONWebKey: Codable, Sendable, Hashable {
    public var kty: String?
    public var crv: String?
    public var x: String?
    public var y: String?
    public var kid: String?
    public var use: String?
    public var alg: String?
}

/// A JWKS document: a set of public keys used to verify the signed Agent Card.
public struct JWKS: Codable, Sendable, Hashable {
    public var keys: [JSONWebKey]

    public init(keys: [JSONWebKey]) {
        self.keys = keys
    }
}

// MARK: - JSONValue

/// A minimal, `Sendable`, `Codable` JSON value used for the dynamic parts of the
/// A2A protocol (JSON-RPC `params` / `result`, Agent Card capabilities, …).
///
/// Supports the full JSON grammar and provides ergonomic accessors and literal
/// conformances so building request params reads naturally:
///
/// ```swift
/// let params: JSONValue = ["message": ["role": "user", "parts": [["text": "hi"]]]]
/// ```
public enum JSONValue: Codable, Sendable, Hashable {
    case null
    case bool(Bool)
    case int(Int)
    case double(Double)
    case string(String)
    case array([JSONValue])
    case object([String: JSONValue])

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let b = try? container.decode(Bool.self) {
            self = .bool(b)
        } else if let i = try? container.decode(Int.self) {
            self = .int(i)
        } else if let d = try? container.decode(Double.self) {
            self = .double(d)
        } else if let s = try? container.decode(String.self) {
            self = .string(s)
        } else if let a = try? container.decode([JSONValue].self) {
            self = .array(a)
        } else if let o = try? container.decode([String: JSONValue].self) {
            self = .object(o)
        } else {
            throw DecodingError.dataCorrupted(
                DecodingError.Context(
                    codingPath: decoder.codingPath,
                    debugDescription: "Unsupported JSON value"
                )
            )
        }
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .null:           try container.encodeNil()
        case .bool(let b):    try container.encode(b)
        case .int(let i):     try container.encode(i)
        case .double(let d):  try container.encode(d)
        case .string(let s):  try container.encode(s)
        case .array(let a):   try container.encode(a)
        case .object(let o):  try container.encode(o)
        }
    }
}

// MARK: - JSONValue ergonomics

public extension JSONValue {
    /// Subscript into an object value. Returns `nil` for non-objects or missing keys.
    subscript(key: String) -> JSONValue? {
        if case .object(let o) = self { return o[key] }
        return nil
    }

    /// Subscript into an array value. Returns `nil` for non-arrays or out-of-range indices.
    subscript(index: Int) -> JSONValue? {
        if case .array(let a) = self, a.indices.contains(index) { return a[index] }
        return nil
    }

    var stringValue: String? {
        if case .string(let s) = self { return s }
        return nil
    }

    var intValue: Int? {
        switch self {
        case .int(let i): return i
        case .double(let d) where d.rounded() == d: return Int(d)
        default: return nil
        }
    }

    var doubleValue: Double? {
        switch self {
        case .double(let d): return d
        case .int(let i): return Double(i)
        default: return nil
        }
    }

    var boolValue: Bool? {
        if case .bool(let b) = self { return b }
        return nil
    }

    var arrayValue: [JSONValue]? {
        if case .array(let a) = self { return a }
        return nil
    }

    var objectValue: [String: JSONValue]? {
        if case .object(let o) = self { return o }
        return nil
    }
}

extension JSONValue: ExpressibleByNilLiteral {
    public init(nilLiteral: ()) { self = .null }
}

extension JSONValue: ExpressibleByBooleanLiteral {
    public init(booleanLiteral value: Bool) { self = .bool(value) }
}

extension JSONValue: ExpressibleByIntegerLiteral {
    public init(integerLiteral value: Int) { self = .int(value) }
}

extension JSONValue: ExpressibleByFloatLiteral {
    public init(floatLiteral value: Double) { self = .double(value) }
}

extension JSONValue: ExpressibleByStringLiteral {
    public init(stringLiteral value: String) { self = .string(value) }
}

extension JSONValue: ExpressibleByArrayLiteral {
    public init(arrayLiteral elements: JSONValue...) { self = .array(elements) }
}

extension JSONValue: ExpressibleByDictionaryLiteral {
    public init(dictionaryLiteral elements: (String, JSONValue)...) {
        self = .object(Dictionary(uniqueKeysWithValues: elements))
    }
}
