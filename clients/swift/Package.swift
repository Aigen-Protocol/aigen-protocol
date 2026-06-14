// swift-tools-version:5.7
//
// OABP Swift SDK — Swift Package manifest.
//
// A typed, async/await client for the OABP / AIGEN agent-bounty protocol
// (https://cryptogenesis.duckdns.org). Pure Foundation (URLSession + Codable),
// no third-party dependencies, so it builds on macOS, iOS, tvOS, watchOS and Linux.

import PackageDescription

let package = Package(
    name: "OABPClient",
    platforms: [
        .macOS(.v12),
        .iOS(.v15),
        .tvOS(.v15),
        .watchOS(.v8)
    ],
    products: [
        .library(
            name: "OABPClient",
            targets: ["OABPClient"]
        )
    ],
    dependencies: [],
    targets: [
        .target(
            name: "OABPClient",
            dependencies: [],
            path: "Sources/OABPClient"
        ),
        .testTarget(
            name: "OABPClientTests",
            dependencies: ["OABPClient"],
            path: "Tests/OABPClientTests"
        )
    ]
)
