import SwiftUI

@main
struct TemperaAirApp: App {
    @StateObject private var model = AppModel()

    var body: some Scene {
        WindowGroup("Tempera Air") {
            ContentView().environmentObject(model)
                .frame(minWidth: 900, minHeight: 600)
                .preferredColorScheme(model.darkMode ? .dark : nil)
        }
        .commands {
            CommandMenu("Emulator") {
                Button("Refresh") { Task { await model.refresh() } }.keyboardShortcut("r")
                Button("Toggle Controls Overlay") { model.showControls.toggle() }
                    .keyboardShortcut(.tab, modifiers: [.shift])
            }
        }
    }
}
