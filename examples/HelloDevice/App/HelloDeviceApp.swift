import SwiftUI

@main
struct HelloDeviceApp: App {
    var body: some Scene {
        WindowGroup { WelcomeView() }
    }
}

private struct WelcomeView: View {
    @Environment(\.locale) private var locale
    @State private var confirmed = false
    private var japanese: Bool { locale.language.languageCode?.identifier == "ja" }

    var body: some View {
        ZStack {
            LinearGradient(colors: [Color.indigo.opacity(0.13), Color.cyan.opacity(0.08), Color.clear],
                           startPoint: .topLeading, endPoint: .bottomTrailing)
                .ignoresSafeArea()
            ScrollView {
                VStack(spacing: 28) {
                    Image(systemName: confirmed ? "checkmark.circle.fill" : "iphone")
                        .font(.system(size: 64, weight: .light))
                        .foregroundStyle(confirmed ? Color.green : Color.indigo)
                        .accessibilityHidden(true)
                    VStack(spacing: 12) {
                        Text(confirmed ? (japanese ? "実機確認できました。" : "You're up and running.") : "Hello, device.")
                            .font(.largeTitle.bold())
                            .multilineTextAlignment(.center)
                        Text(japanese ? "ひとつのコマンドから、あなたの画面へ。" : "From one command to your screen.")
                            .font(.title3)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    VStack(alignment: .leading, spacing: 18) {
                        Label(japanese ? "Xcodeでビルド" : "Built with Xcode", systemImage: "hammer")
                        Label(japanese ? "この端末にインストール" : "Installed on this device", systemImage: "arrow.down.app")
                        Label(japanese ? "アプリを起動" : "Launched and ready", systemImage: "play.circle")
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(24)
                    .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 24))
                    Button {
                        withAnimation(.easeInOut(duration: 0.2)) { confirmed.toggle() }
                    } label: {
                        Text(confirmed ? (japanese ? "もう一度" : "Try again") : (japanese ? "表示とタップを確認" : "Confirm display and touch"))
                            .font(.headline)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 10)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.indigo)
                    Text("ios-one-command · HelloDevice")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: 440)
                .padding(28)
                .padding(.top, 36)
                .frame(maxWidth: .infinity)
            }
        }
    }
}
