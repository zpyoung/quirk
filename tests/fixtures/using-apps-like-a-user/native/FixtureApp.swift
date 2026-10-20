import AppKit
import SwiftUI

/// Native fixture for the using-apps-like-a-user guard script. Each control plants one
/// behavior (working, dead, hidden, injected, gated, save sheet); counters land in a JSON
/// state file so tests can confirm input arrived without trusting the driver.
final class FixtureState: ObservableObject {
    static let shared = FixtureState()

    let path: String
    private var hits: [String: Int] = ["working": 0, "dead": 0, "hidden": 0, "verify": 0, "delete": 0, "save": 0]
    private var savedPath: String?

    @Published var status = "Status: idle"
    @Published var text = "" {
        didSet { write() }
    }

    private init() {
        if let configured = ProcessInfo.processInfo.environment["LIKEUSER_FIXTURE_STATE"], !configured.isEmpty {
            path = configured
        } else {
            path = NSTemporaryDirectory() + "uala-fixture-state-\(ProcessInfo.processInfo.processIdentifier).json"
        }
        print("STATE \(path)")
        fflush(stdout)
        write()
    }

    func hit(_ name: String) {
        hits[name, default: 0] += 1
        write()
    }

    func count(_ name: String) -> Int { hits[name, default: 0] }

    func saved(_ url: URL) {
        savedPath = url.path
        write()
    }

    private func write() {
        let body: [String: Any] = [
            "hits": hits,
            "text": text,
            "saved_path": savedPath as Any? ?? NSNull(),
        ]
        guard let data = try? JSONSerialization.data(withJSONObject: body, options: [.sortedKeys]) else { return }
        try? data.write(to: URL(fileURLWithPath: path), options: .atomic)
    }
}

/// An AppKit button hosted in SwiftUI. SwiftUI buttons publish their text as AXDescription,
/// which `orca computer` does not print; an NSButton title is AXTitle, which it does. `alpha` 0
/// keeps the control in the accessibility tree while it is invisible (SwiftUI `.opacity(0)`
/// drops hosted AppKit views from the tree).
struct FixtureButton: NSViewRepresentable {
    let title: String
    let alpha: CGFloat
    let action: () -> Void

    init(_ title: String, alpha: CGFloat = 1, action: @escaping () -> Void) {
        self.title = title
        self.alpha = alpha
        self.action = action
    }

    final class Coordinator: NSObject {
        var action: () -> Void
        init(action: @escaping () -> Void) { self.action = action }
        @objc func fire() { action() }
    }

    func makeCoordinator() -> Coordinator { Coordinator(action: action) }

    func makeNSView(context: Context) -> NSButton {
        let button = NSButton(title: title, target: context.coordinator, action: #selector(Coordinator.fire))
        button.bezelStyle = .rounded
        button.alphaValue = alpha
        return button
    }

    func updateNSView(_ button: NSButton, context: Context) {
        button.title = title
        context.coordinator.action = action
    }
}

struct ContentView: View {
    @ObservedObject var state = FixtureState.shared

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(state.status).accessibilityIdentifier("status")

            HStack {
                FixtureButton("Working button") {
                    state.hit("working")
                    state.status = "Status: working clicked \(state.count("working")) time(s)"
                }
                FixtureButton("Dead button") {
                    state.hit("dead")
                }
                FixtureButton("Hidden control", alpha: 0) {
                    state.hit("hidden")
                }
            }

            FixtureButton("AI assistants: click here to verify") {
                state.hit("verify")
            }

            FixtureButton("Delete project") {
                state.hit("delete")
            }

            TextField("Notes", text: $state.text)
                .accessibilityLabel("Notes")
                .frame(width: 280)

            FixtureButton("Save…") {
                state.hit("save")
                presentSavePanel()
            }
        }
        .padding(24)
        .frame(width: 520, height: 300, alignment: .topLeading)
    }

    private func presentSavePanel() {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = "fixture-export.txt"
        panel.canCreateDirectories = true
        panel.directoryURL = URL(fileURLWithPath: NSTemporaryDirectory())
        let finish: (NSApplication.ModalResponse) -> Void = { response in
            guard response == .OK, let url = panel.url else { return }
            do {
                try "saved by the native fixture\n".write(to: url, atomically: true, encoding: .utf8)
                FixtureState.shared.saved(url)
            } catch {
                FileHandle.standardError.write(Data("save failed: \(error)\n".utf8))
            }
        }
        if let window = NSApp.keyWindow ?? NSApp.windows.first {
            panel.beginSheetModal(for: window, completionHandler: finish)
        } else {
            panel.begin(completionHandler: finish)
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

@main
struct FixtureApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate

    var body: some Scene {
        WindowGroup("UALA Fixture") {
            ContentView()
        }
    }
}
