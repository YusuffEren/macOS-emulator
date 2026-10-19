import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var model: AppModel

    var body: some View {
        NavigationSplitView {
            List {
                NavigationLink("Library", destination: LibraryView())
                NavigationLink("Instances", destination: InstancesView())
                NavigationLink("Backups", destination: BackupsView())
                NavigationLink("Macros", destination: MacrosView())
                NavigationLink("Settings", destination: SettingsView())
                NavigationLink("Diagnostics", destination: DiagnosticsView())
            }
            .navigationTitle("Tempera Air")
        } detail: {
            LibraryView()
        }
        .task { await model.refresh() }
        .overlay(alignment: .trailing) {
            if model.showControls { ControlsOverlay().transition(.move(edge: .trailing)) }
        }
        .alert("Tempera Air", isPresented: Binding(get: { model.errorMessage != nil }, set: { if !$0 { model.errorMessage = nil } })) {
            Button("OK") { model.errorMessage = nil }
        } message: { Text(model.errorMessage ?? "") }
    }
}

struct LibraryView: View {
    @EnvironmentObject private var model: AppModel
    var body: some View {
        VStack(alignment: .leading) {
            Text("Personal Library").font(.largeTitle.bold())
            if model.library.isEmpty { ContentUnavailableView("No apps", systemImage: "square.grid.2x2", description: Text("Add packages with android-sim library add.")) }
            else {
                List(Array(model.library.enumerated()), id: \.offset) { _, app in
                    HStack {
                        Image(systemName: "gamecontroller.fill")
                        VStack(alignment: .leading) {
                            Text(app.string("title") ?? "Android app")
                            Text(app.string("package") ?? "").foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }.padding()
    }
}

struct InstancesView: View {
    @EnvironmentObject private var model: AppModel
    var body: some View {
        VStack(alignment: .leading) {
            HStack {
                Text("Instances").font(.largeTitle.bold())
                Spacer()
                Button("Arrange in Grid") { Task { await model.arrangeInstances() } }
                    .disabled(model.instances.count < 2)
            }
            List(model.instances, id: \.self) { name in
                HStack {
                    Image(systemName: "iphone.gen3")
                    Text(name)
                    Spacer()
                    Button("Back Up") { Task { await model.createBackup(name) } }
                    Button("Start") { Task { await model.startInstance(name) } }
                }
            }
        }.padding()
    }
}

struct BackupsView: View {
    @EnvironmentObject private var model: AppModel
    var body: some View {
        VStack(alignment: .leading) {
            Text("Backups").font(.largeTitle.bold())
            if model.backups.isEmpty { ContentUnavailableView("No backups", systemImage: "externaldrive.badge.timemachine", description: Text("Create one from an instance with the Back Up button.")) }
            else {
                List(Array(model.backups.enumerated()), id: \.offset) { _, backup in
                    HStack {
                        Image(systemName: "externaldrive.badge.timemachine")
                        VStack(alignment: .leading) {
                            Text(backup.string("instance") ?? "instance")
                            Text(backup.string("created_at") ?? "").foregroundStyle(.secondary)
                        }
                        Spacer()
                        Text(backup.number("bytes").map { ByteCountFormatter.string(fromByteCount: Int64($0), countStyle: .file) } ?? "")
                            .foregroundStyle(.secondary)
                        Button("Verify") { Task { await model.verifyBackup(backup.string("backup_id") ?? "") } }
                    }
                }
            }
        }.padding().task { await model.refresh() }
    }
}

struct MacrosView: View {
    @EnvironmentObject private var model: AppModel
    @State private var draftName = ""
    var body: some View {
        VStack(alignment: .leading) {
            Text("Macros").font(.largeTitle.bold())
            GroupBox("Recording") {
                if let recording = model.recordingName {
                    LabeledContent("Recording", value: recording)
                    HStack {
                        Button("Stop & Save") { Task { await model.stopRecording() } }
                        Button("Cancel") { Task { await model.cancelRecording() } }
                    }
                } else {
                    HStack {
                        TextField("Macro name", text: $draftName)
                        Button("Start Recording") {
                            let trimmed = draftName.trimmingCharacters(in: .whitespaces)
                            guard !trimmed.isEmpty else { return }
                            Task { await model.startRecording(trimmed) }
                        }
                    }
                    Text("Actions executed through the guarded agent are captured while a session is open.")
                        .foregroundStyle(.secondary)
                }
            }
            if model.macros.isEmpty { ContentUnavailableView("No macros", systemImage: "film", description: Text("Record a session or import one with android-sim macro import.")) }
            else {
                List(Array(model.macros.enumerated()), id: \.offset) { _, macro in
                    HStack {
                        Image(systemName: "film")
                        VStack(alignment: .leading) {
                            Text(macro.string("name") ?? "macro")
                            Text("\(Int(macro.number("steps") ?? 0)) steps").foregroundStyle(.secondary)
                        }
                        Spacer()
                        Button("Run on All Running") { Task { await model.runMacro(macro.string("name") ?? "", onAllRunning: true) } }
                    }
                }
            }
        }.padding().task { await model.refresh() }
    }
}

struct SettingsView: View {
    @EnvironmentObject private var model: AppModel
    var body: some View {
        Form {
            Toggle("Dark mode", isOn: $model.darkMode)
            Toggle("Controls overlay", isOn: $model.showControls)
            LabeledContent("Engine", value: model.engineSummary)
            LabeledContent("Last action", value: model.statusMessage ?? "—")
            Text("Per-instance CPU, RAM, resolution, DPI, FPS, eco mode, V-Sync, and window placement are managed by the versioned CLI contract.")
                .foregroundStyle(.secondary)
        }.padding().navigationTitle("Settings")
    }
}

struct DiagnosticsView: View {
    @EnvironmentObject private var model: AppModel
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Diagnostics").font(.largeTitle.bold())
            LabeledContent("Engine", value: model.engineSummary)
            LabeledContent("Last action", value: model.statusMessage ?? "—")
            Button("Refresh") { Task { await model.refresh() } }
            if model.isBusy { ProgressView() }
            Spacer()
        }.padding()
    }
}

struct ControlsOverlay: View {
    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: "keyboard")
            Button(action: {}) { Image(systemName: "arrow.up.left.and.arrow.down.right") }
            Button(action: {}) { Image(systemName: "rotate.right") }
            Button(action: {}) { Image(systemName: "camera") }
            Button(action: {}) { Image(systemName: "mic") }
            Button(action: {}) { Image(systemName: "folder") }
            Button(action: {}) { Image(systemName: "gearshape") }
        }
        .buttonStyle(.borderless).padding(12).background(.ultraThinMaterial).clipShape(RoundedRectangle(cornerRadius: 14)).padding()
    }
}

private extension Dictionary where Key == String, Value == JSONValue {
    func string(_ key: String) -> String? {
        if case let .string(value)? = self[key] { return value }
        return nil
    }

    func number(_ key: String) -> Double? {
        if case let .number(value)? = self[key] { return value }
        return nil
    }
}
