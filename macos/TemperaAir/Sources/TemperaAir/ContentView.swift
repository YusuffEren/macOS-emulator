import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var model: AppModel

    var body: some View {
        NavigationSplitView {
            List {
                NavigationLink("Library", destination: LibraryView())
                NavigationLink("Instances", destination: InstancesView())
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
            Text("Instances").font(.largeTitle.bold())
            List(model.instances, id: \.self) { name in
                HStack { Image(systemName: "iphone.gen3"); Text(name); Spacer(); Button("Start") {} }
            }
        }.padding()
    }
}

struct SettingsView: View {
    @EnvironmentObject private var model: AppModel
    var body: some View {
        Form {
            Toggle("Dark mode", isOn: $model.darkMode)
            Toggle("Controls overlay", isOn: $model.showControls)
            LabeledContent("Engine", value: model.engineSummary)
            Text("Per-instance CPU, RAM, resolution, DPI, renderer, FPS and V-Sync are managed by the versioned CLI contract.")
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
}
