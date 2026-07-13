// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "Sandwalk",
    platforms: [.macOS(.v14)],
    products: [
        .library(name: "SandwalkCore", targets: ["SandwalkCore"]),
        .executable(name: "Sandwalk", targets: ["Sandwalk"]),
    ],
    targets: [
        // Library holds app logic + UI so tests can `@testable import SandwalkCore`.
        // Executable is a thin `@main` entry point.
        .target(
            name: "SandwalkCore",
            path: "Sources/SandwalkCore",
            resources: [
                .process("Resources"),
            ]
        ),
        .executableTarget(
            name: "Sandwalk",
            dependencies: ["SandwalkCore"],
            path: "Sources/SandwalkApp"
        ),
        .testTarget(
            name: "SandwalkTests",
            dependencies: ["SandwalkCore"],
            path: "Tests/SandwalkTests"
        ),
    ]
)
