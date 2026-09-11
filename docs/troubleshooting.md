# Troubleshooting / 困ったとき

Run `bash ios-one doctor --lang ja` for environment inspection. It does not build
an app. Each workflow prints its local log folder on completion or failure.

| Code / symptom | What to do / 対応 |
| --- | --- |
| `PLATFORM` | Run on a Mac with Xcode. / XcodeのあるMacで実行してください。 |
| `XCODE`, `XCODE_VERSION` | Install full Xcode and finish setup. Use `--xcode` to select it. / Xcode本体を準備し、必要なら`--xcode`で指定。 |
| `xcode-first-launch` | Open Xcode, accept its license yourself and install required components. / Xcodeを開いて初回設定を完了。 |
| `TARGET_UNAVAILABLE` | Connect/unlock/trust the device; use `--device` or `--simulator` to reselect. / 接続・ロック解除・信頼を確認。 |
| Developer Mode | Check device Settings > Privacy & Security > Developer Mode. / 端末の設定 → プライバシーとセキュリティ → デベロッパモード。 |
| `AMBIGUOUS` | Pass `--scheme`, `--device ID`, `--simulator ID`, `--app-target` or `--team` as appropriate. / 該当オプションで候補を明示。 |
| `SCHEME` | Share the scheme in Xcode Manage Schemes, or choose another. / Schemeを共有し直すか選び直す。 |
| `SIGNING_SETUP` | Xcode Settings > Accounts, then Signing & Capabilities > Team. / ログインとTeamを設定。 |
| No Account for Team | Check Xcode login for the selected Team; override with `--team` only when intended. / Teamに対応するログインを確認。 |
| `MULTI_BUNDLE` | Set bundle identifiers per target in Xcode; omit `--bundle-id`. / 複数BundleのIDはXcode側で設定。 |
| `MULTI_TEAM` | Set each target's signing in Xcode, or explicitly override the scheme with `--team`. / 各ターゲットの署名を設定。 |
| `IOS_VERSION` | Use an OS at least as new as the app's deployment target. / アプリの最低OS以上の端末を選択。 |
| `resolve-packages` | Check network access, repository credentials and package versions. / 通信・依存リポジトリの権限を確認。 |
| `build` | Read the first compiler error in the build log. / 最初のコンパイルエラーを確認。 |
| `PRODUCT_PATH` | Custom product output locations are not supported in this preview. / 独自ビルド出力先は未対応。 |
| `BUSY` | Wait for the other run to finish; locks release automatically. / 同じプロジェクトの実行終了を待つ。 |
| `TIMEOUT` | Inspect the stalled step, retry, or set `--timeout 3600`. / 停止工程を確認して再実行。 |
| Installer says existing file changed | Keep your edited folder; use a separately extracted source ZIP. / 編集を保持し、別フォルダへZIPを展開。 |

To change a saved choice, pass the corresponding option. To clear all remembered
choices for a project, move its `settings.json` out of the state folder printed in
the log path; keep it as a backup. DerivedData and source files can remain intact.
Changing `IOS_ONE_HOME` also starts with an independent state directory.

For an issue report:

```bash
bash ios-one report --project "/path/to/MyApp.xcodeproj" --output report.json
```

The output file must not already exist. The report excludes identifying fields.
No upload or message is sent. Review it and attach it yourself when reporting.

For local command help matching the actual installed Xcode:

```bash
xcodebuild -help
xcrun devicectl device install app --help
xcrun devicectl device process launch --help
xcrun simctl help
```
