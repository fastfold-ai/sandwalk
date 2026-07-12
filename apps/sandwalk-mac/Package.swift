// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "Sandwalk",
    platforms: [.macOS(.v14)],
    products: [
        .executable(name: "Sandwalk", targets: ["Sandwalk"]),
    ],
    targets: [
        .executableTarget(
            name: "Sandwalk",
            path: "Sources/Sandwalk",
            resources: [
                .process("Resources"),
            ]
        ),
    ]
)
