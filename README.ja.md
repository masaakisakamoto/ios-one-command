# ios-one-command

**ひとつのコマンドで、iOSプロジェクトから実機起動まで。**

[English](README.md) · [困ったとき](docs/troubleshooting.md) · [検証状況](docs/validation.md)

AIと一緒に作ったアプリなどを、自分のiPhoneですぐに試すための小さな開発ツールです。
Xcode確認、端末選択、署名設定の確認、ビルド、インストール、起動をまとめます。
案内は日本語・英語に対応しています。

**現在は0.1.0-preview.1です。１環境でのiPhone実機確認ができました。**
2026-09-11に提供された実行ログで、**Xcode 26.2（17C52）・iOS 26.6.1（23G83）**での
ビルド・インストール・起動の成功を確認しました。操作前後のスクリーンショットで、
サンプルの画面表示と確認ボタンによる状態の切り替えも確認しています。
GitHub CIではLinux・macOSの自動テストと、iPhone Simulatorでのビルド・インストール・起動も成功しました。
別の開発者のMacや既存の別プロジェクトでの確認は、これからです。
詳しくは[検証記録](docs/validation.md)を参照してください。

## まず試す

必要なものは、Xcode 15以降が使えるMac、Python 3.9以降、iOS/iPadOS 17以降のiPhone/iPadです。
Mac・端末のOSに対応したXcodeを使い、最初にXcodeを一度開いて初回設定を完了してください。

[IOS_One_Command_Start.commandをダウンロード](https://github.com/masaakisakamoto/ios-one-command/releases/download/v0.1.0-preview.1/IOS_One_Command_Start.command)して、ターミナルで実行します。

```bash
bash "$HOME/Downloads/IOS_One_Command_Start.command"
```

この１ファイルにソースが含まれており、`~/Dev/ios-one-command`に準備して、
サンプルアプリ「HelloDevice」を起動します。別途ZIPを用意する必要はありません。
初回に端末やTeamの候補が複数あれば、番号で選択します。

初回の実機準備は、端末の接続・ロック解除、Macを信頼する操作、デベロッパモード、
XcodeのApple Accountへのログインです。これらの本人操作は自動で済ませません。
問題があれば、確認先を表示します。

[ソースZIP](https://github.com/masaakisakamoto/ios-one-command/releases/download/v0.1.0-preview.1/ios-one-command-0.1.0-preview.1.zip)を展開して使う場合は、そのフォルダで実行します。

```bash
bash Try_Demo.command --lang ja
```

[リリース内容・チェックサム](https://github.com/masaakisakamoto/ios-one-command/releases/tag/v0.1.0-preview.1)も公開しています。
すでに導入済みで内容が異なる場合、単体ランチャーは停止します。
その場合はZIPを別フォルダに展開し、上のコマンドで試せます。

Simulatorで試す場合はこちらです。

```bash
bash Try_Demo.command --simulator --lang ja
```

サンプルには自分用の開発Bundle IDを生成し、次回も再利用します。
端末に「Hello, device.」が表示されたら、「表示とタップを確認」を押してください。
アプリ内の日本語・英語は端末の言語に従います。CLIの`--lang`とは別です。

## 自分のアプリで使う

ツールのフォルダから実行する例です。

```bash
bash ios-one run --project "/path/to/MyApp.xcodeproj" --scheme MyApp --lang ja
```

`.xcworkspace`にも対応します。CocoaPodsやFlutterなど、プロジェクト固有の準備は先に済ませてください。
Swift Package Managerの依存解決は、処理中にXcodeを使って実行します。

```bash
bash ios-one run --project "/path/to/MyApp.xcworkspace" --scheme MyApp --device "端末ID" --lang ja
```

アプリのフォルダから`ios-one`の絶対パスを指定した場合、そのフォルダ直下のXcodeプロジェクトを検出します。
複数のアプリがあるフォルダを再帰的に探索して、勝手に選ぶことはありません。

| 操作 | コマンド |
| --- | --- |
| 実機で起動 | `bash ios-one run --project "…"` |
| サンプルを起動 | `bash Try_Demo.command --lang ja` |
| 環境・端末・署名の確認 | `bash ios-one doctor --lang ja` |
| Simulator向けビルドのみ | `bash ios-one verify --project "…" --lang ja` |
| 保存済みの端末を選び直す | `--device`または`--simulator`を付ける |
| Teamを明示する | `--team 実際の10桁のTeamID` |
| 複数候補があるとき自動実行を止める | `--no-input`を付ける |
| 自動テストでSimulatorの画面を開かず起動 | `run/demo --simulator`に`--headless`を付ける |
| 別のXcodeを使う | `--xcode /Applications/Xcode.app` |

Scheme・端末などの選択は次回に引き継ぎます。保存した端末が使えないときは案内して停止します。
初回に実機が見つからない場合も、Simulatorへの切り替えは`--simulator`で明示します。

CIは`--headless`でビルド・インストール・アプリ起動を確認します。
起動やインストールの失敗は停止します。画面表示・タッチ操作は別途確認が必要です。

既存のXcodeプロジェクトに署名設定がある場合はそれを使います。
`--team`を指定した場合は、選択Scheme全体のTeamと自動署名を上書き指定します。
証明書からTeamを判定する場合は、表示名の末尾でなく証明書のOUを読みます。

`--bundle-id`は、Bundleが１つのSchemeでのみ利用できます。
Widget・拡張・フレームワークなどがある場合は、Xcodeで各ターゲットに個別のIDを設定してください。

## 既存作業と保存先

ツールの設定・ビルドキャッシュ・ログは、アプリの外に保存します。

```text
~/Library/Application Support/ios-one-command/<project-key>/
```

ツールは既存アプリのソースや`.pbxproj`を書き換えません。
ただし、実行されるXcode自身は`Package.resolved`等の更新、依存取得、ビルドスクリプトの実行、
自動署名に必要なプロファイル更新・開発端末の登録などを行う場合があります。
起動時には選択したアプリをインストールし、既存のアプリプロセスを再起動します。

単体ランチャーは、同じ内容の導入済みファイルを再利用します。
導入先でソースを編集していた場合、上書きせず停止します。
この初版は、既存ツールへの自動更新・差分マージは行いません。

利用状況の送信やAI API呼び出し、秘密鍵の書き出し、ログの自動アップロードはありません。
生のXcodeログは個人情報を含む場合があるため、不具合報告には`shareable-report.json`を使ってください。
共有用レポートは、パス・端末名/ID・Team ID・証明書・生のエラー内容を含めない形式です。

## 公開と今後の進め方

まずサンプルの実機確認、その後に既存アプリでの確認を行います。
GitHub公開用に、MITライセンス、日英README、CI、不具合報告フォーム、公開コマンドを同梱しています。

- [Macでの検証記録](docs/validation.md)
- [GitHubに公開する手順](docs/publishing.md)
- [デモ動画の撮影手順](docs/demo-recording.md)

この初版の対象は、準備済みプロジェクトのローカル実機起動です。
TestFlightへの配布・審査申請やApp Storeへの公開は、今後の別機能として扱います。

masaaki officeがAI支援を用いて開発。MITライセンス。
