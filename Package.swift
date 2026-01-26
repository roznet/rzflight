// swift-tools-version:5.5
// The swift-tools-version declares the minimum version of Swift required to build this package.

import PackageDescription

let package = Package(
    name: "RZFlight",
    platforms: [
        .macOS(.v12), .iOS(.v15)
    ],
    products: [
        // Products define the executables and libraries a package produces, and make them visible to other packages.
        .library(
            name: "RZFlight",
            targets: ["RZFlight"]),
    ],
    dependencies: [
        // Dependencies declare other packages that this package depends on.
        .package(name: "RZUtils", url: "https://github.com/roznet/rzutils", from: "1.0.27"),
        .package(name: "Geomagnetism", url: "https://github.com/roznet/Geomagnetism", from: "1.0.0"),
        .package(name: "FMDB", url: "https://github.com/ccgus/fmdb", from: "2.7.7"),
        .package(name: "KDTree", url: "https://github.com/Bersaelor/KDTree.git", from: "1.4.0")
    ],
    targets: [
        // Targets are the basic building blocks of a package. A target can define a module or a test suite.
        // Targets can depend on other targets in this package, and on products in packages this package depends on.
        .target(
            name: "RZFlight",
            dependencies: [
                .product(name: "RZUtilsSwift", package: "RZUtils"),
                .product(name: "Geomagnetism", package: "Geomagnetism"),
                .product(name: "KDTree", package: "KDTree"),
                .product(name: "FMDB", package: "FMDB")
            ],
            resources: [
                .process("Resources/aip_fields.csv"),
                .process("Resources/q_codes.json")
            ]
        ),
        .testTarget(
            name: "RZFlightTests",
            dependencies: ["RZFlight"],
            exclude: [ "samples"]
        ),
        
    ]
)
