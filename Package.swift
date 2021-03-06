// swift-tools-version:5.3
// The swift-tools-version declares the minimum version of Swift required to build this package.

import PackageDescription

let package = Package(
    name: "RZFlight",
    platforms: [
        .macOS(.v11), .iOS(.v14)
    ],
    products: [
        // Products define the executables and libraries a package produces, and make them visible to other packages.
        .library(
            name: "RZFlight",
            targets: ["RZFlight"]),
    ],
    dependencies: [
        // Dependencies declare other packages that this package depends on.
        .package(name: "Geomagnetism", url: "https://github.com/roznet/Geomagnetism", from: "1.0.0"),
        .package(name: "FMDB", url: "https://github.com/ccgus/fmdb", from: "2.7.7")
    ],
    targets: [
        // Targets are the basic building blocks of a package. A target can define a module or a test suite.
        // Targets can depend on other targets in this package, and on products in packages this package depends on.
        .target(
            name: "RZFlight",
            dependencies: [ .product(name: "Geomagnetism", package: "Geomagnetism"), .product(name: "FMDB", package: "FMDB") ] ),
        .testTarget(
            name: "RZFlightTests",
            dependencies: ["RZFlight"],
            exclude: [ "samples"]
        ),
        
    ]
)
