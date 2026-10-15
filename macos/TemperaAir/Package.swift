// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "TemperaAir",
    platforms: [.macOS(.v14)],
    products: [.executable(name: "TemperaAir", targets: ["TemperaAir"])],
    targets: [.executableTarget(name: "TemperaAir")]
)
