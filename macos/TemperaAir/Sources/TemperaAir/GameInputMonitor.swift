import AppKit
import GameController

@MainActor
final class GameInputMonitor: ObservableObject {
    @Published private(set) var controllerName: String?
    @Published var enabled = false

    init() {
        NotificationCenter.default.addObserver(
            forName: .GCControllerDidConnect,
            object: nil,
            queue: .main
        ) { [weak self] notification in
            guard let controller = notification.object as? GCController else { return }
            self?.controllerName = controller.vendorName
        }
        NotificationCenter.default.addObserver(
            forName: .GCControllerDidDisconnect,
            object: nil,
            queue: .main
        ) { [weak self] _ in self?.controllerName = nil }
    }

    func shouldForwardInput() -> Bool {
        enabled && NSApplication.shared.isActive && NSApplication.shared.keyWindow != nil
    }
}
