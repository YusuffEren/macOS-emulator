import SwiftUI

@MainActor
final class AppModel: ObservableObject {
    @Published var instances: [String] = []
    @Published var library: [[String: JSONValue]] = []
    @Published var engineSummary = "Not checked"
    @Published var errorMessage: String?
    @Published var isBusy = false
    @Published var darkMode = true
    @Published var showControls = false
    private let client = CLIClient()

    func refresh() async {
        isBusy = true
        defer { isBusy = false }
        do {
            async let instanceEnvelope = client.run(["instance", "list"])
            async let libraryEnvelope = client.run(["library", "list"])
            async let engineEnvelope = client.run(["engine", "status"])
            let (instanceResult, libraryResult, engineResult) = try await (instanceEnvelope, libraryEnvelope, engineEnvelope)
            if case let .object(object)? = instanceResult.data,
               case let .array(values)? = object["avds"] {
                instances = values.compactMap { if case let .string(value) = $0 { return value }; return nil }
            }
            if case let .array(values)? = libraryResult.data {
                library = values.compactMap { if case let .object(value) = $0 { return value }; return nil }
            }
            if case let .object(value)? = engineResult.data,
               case let .bool(installed)? = value["installed"] {
                engineSummary = installed ? "Pinned custom engine installed" : "Using SDK emulator fallback"
            }
            errorMessage = nil
        } catch {
            errorMessage = String(describing: error)
        }
    }
}
