import SwiftUI

@MainActor
final class AppModel: ObservableObject {
    @Published var instances: [String] = []
    @Published var library: [[String: JSONValue]] = []
    @Published var backups: [[String: JSONValue]] = []
    @Published var macros: [[String: JSONValue]] = []
    @Published var recordingName: String?
    @Published var engineSummary = "Not checked"
    @Published var errorMessage: String?
    @Published var statusMessage: String?
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
            async let backupEnvelope = client.run(["backup", "list"])
            async let macroEnvelope = client.run(["macro", "list"])
            async let recordEnvelope = client.run(["macro", "record", "status"])
            let (instanceResult, libraryResult, engineResult, backupResult, macroResult, recordResult) =
                try await (instanceEnvelope, libraryEnvelope, engineEnvelope, backupEnvelope, macroEnvelope, recordEnvelope)
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
            if case let .array(values)? = backupResult.data {
                backups = values.compactMap { if case let .object(value) = $0 { return value }; return nil }
            }
            if case let .array(values)? = macroResult.data {
                macros = values.compactMap { if case let .object(value) = $0 { return value }; return nil }
            }
            if case let .object(value)? = recordResult.data,
               case let .bool(recording)? = value["recording"], recording,
               case let .string(name)? = value["name"] {
                recordingName = name
            } else {
                recordingName = nil
            }
            errorMessage = nil
        } catch {
            errorMessage = String(describing: error)
        }
    }

    func startInstance(_ name: String) async {
        await runCommand(["start", name, "--no-wait"], success: "Started \(name)")
    }

    func arrangeInstances() async {
        guard instances.count > 1 else { return }
        await runCommand(["instance", "arrange"] + instances, success: "Arranged \(instances.count) instances in a grid")
    }

    func createBackup(_ name: String) async {
        await runCommand(["backup", "create", name], success: "Backed up \(name)")
    }

    func verifyBackup(_ backupId: String) async {
        await runCommand(["backup", "verify", backupId], success: "Backup \(backupId) verified")
    }

    func startRecording(_ name: String) async {
        await runCommand(["macro", "record", "start", "--name", name], success: "Recording \(name)")
    }

    func stopRecording() async {
        await runCommand(["macro", "record", "stop"], success: "Recording saved as a macro")
    }

    func cancelRecording() async {
        await runCommand(["macro", "record", "cancel"], success: "Recording cancelled")
    }

    func runMacro(_ name: String, onAllRunning: Bool) async {
        var arguments = ["macro", "run", name]
        if onAllRunning { arguments.append("--all-running") }
        await runCommand(arguments, success: "Ran macro \(name)")
    }

    private func runCommand(_ arguments: [String], success: String) async {
        isBusy = true
        defer { isBusy = false }
        do {
            _ = try await client.run(arguments)
            statusMessage = success
            errorMessage = nil
            await refresh()
        } catch {
            errorMessage = String(describing: error)
        }
    }
}
