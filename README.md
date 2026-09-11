# ios-one-command

**From an iOS project to a running app, with one command.**

[日本語](README.ja.md) · [Troubleshooting](docs/troubleshooting.md) · [Validation status](docs/validation.md)

An approachable launcher for developers who want to try an iOS app on their own
device, including apps built with AI assistance. It checks Xcode, helps select a
device and signing Team, builds the selected scheme, installs the app and launches
it. English and Japanese guidance is included.

**0.1.0-preview.1 — early preview with one reported physical-device smoke test.**
On 2026-09-11, the supplied run log showed a successful build, install and launch
with **Xcode 26.2 (17C52)** and **iOS 26.6.1 (23G83)**. Before/after screenshots
also confirmed the HelloDevice screen and confirmation-button state change.
GitHub CI also passed on Linux and macOS, including a build/install/launch on an
iPhone Simulator. A second developer's Mac and existing third-party projects
remain unverified. See the [validation record](docs/validation.md).

## Try the included app

Requirements: a Mac with full Xcode 15 or later, Python 3.9 or later, and an
iPhone/iPad running iOS/iPadOS 17 or later. The installed Xcode must support both
your Mac and your device OS. Complete Xcode's initial setup first.

Download the standalone [IOS_One_Command_Start.command](https://github.com/masaakisakamoto/ios-one-command/releases/download/v0.1.0-preview.1/IOS_One_Command_Start.command) and run:

```bash
bash "$HOME/Downloads/IOS_One_Command_Start.command"
```

Or download and extract the [source ZIP](https://github.com/masaakisakamoto/ios-one-command/releases/download/v0.1.0-preview.1/ios-one-command-0.1.0-preview.1.zip), then run in the extracted folder:

```bash
bash Try_Demo.command
```

[Release notes and checksums](https://github.com/masaakisakamoto/ios-one-command/releases/tag/v0.1.0-preview.1)
are available with the downloads. Existing installations with different files are
preserved; extract the source ZIP into a separate folder to try this release.

The standalone file contains the source distribution. It installs under
`~/Dev/ios-one-command` and launches **HelloDevice**, a small SwiftUI demo.
No companion ZIP, pip packages, Ruby, Homebrew, or XcodeGen is needed for the
launcher itself. Python and full Xcode must already be available.

For the first device run, connect and unlock your device, trust the Mac, enable
Developer Mode, and sign in to your Apple Account in Xcode. The launcher guides
you when signing needs attention. These initial account/device steps are not
automatically accepted on your behalf.

Use `--simulator` to explicitly try a Simulator:

```bash
bash Try_Demo.command --simulator
```

HelloDevice gets a unique development bundle ID saved locally. Repeated runs reuse
it. Tap **Confirm display and touch** after launch to check the visible UI.

## Run your existing project

From this tool's folder:

```bash
bash ios-one run --project "/path/to/MyApp.xcodeproj" --scheme MyApp
```

Workspaces are supported too. Prepare any CocoaPods, Flutter, React Native, or
other generator-specific setup using that project's own instructions first.
Swift Package Manager resolution is handled by Xcode during the workflow.

```bash
bash ios-one run --project "/path/to/MyApp.xcworkspace" --scheme MyApp --device "DEVICE-ID"
bash ios-one run --project "/path/to/MyApp.xcodeproj" --scheme MyApp --simulator
```

When called from a project's folder using the absolute path to `ios-one`, the
launcher detects a workspace/project in that folder. It does not recursively
guess across a directory of unrelated projects. Shared schemes are recommended.

Device/scheme choices are remembered. Multiple device, scheme, app-target, or Team
candidates are presented for selection. `--no-input` stops on ambiguity. A missing
saved device stops with guidance; another device is not silently substituted.

## Commands

| Command | Behavior |
| --- | --- |
| `run` | Build, install and launch an existing project |
| `demo` | Build, install and launch HelloDevice |
| `doctor` | Inspect Xcode, available devices and public signing certificates |
| `verify --project …` | Build for a generic iOS Simulator, without installing |
| `report --project …` | Print the latest report with identifying fields excluded |

Common options: `--project`, `--scheme`, `--device [ID_OR_NAME]`,
`--simulator [ID_OR_NAME]`, `--app-target`, `--team`, `--configuration`,
`--xcode`, `--no-input`, `--lang ja|en`, `--timeout SECONDS`.

For automation, add `--headless` to `run/demo --simulator` to build, install and
launch without opening the Simulator window. Boot and launch failures still stop
the command. The CI smoke check uses this mode; it does not verify visible UI.

```bash
bash ios-one doctor --lang ja
bash ios-one run --project "/path/to/MyApp.xcodeproj" --team YOURTEAMID
bash ios-one run --project "/path/to/MyApp.xcodeproj" --xcode /Applications/Xcode.app
bash ios-one run --project "/path/to/MyApp.xcodeproj" -- -AppleLanguages '(ja)'
```

Replace `YOURTEAMID` with your actual 10-character Team ID. `--team` explicitly
overrides signing across the selected scheme. Otherwise, existing project signing
settings are preserved. Certificate fallback reads the Team from the certificate's
**OU**, not from a developer display-name suffix.

`--bundle-id org.example.myapp` applies only to a scheme producing a single bundle.
It is rejected for schemes with other bundles, including app extensions and
frameworks, to prevent a global override assigning them the same identifier.
For those projects, set each bundle's ID in Xcode.

## What changes on your Mac

The launcher stores settings, a per-project lock, dependency checkouts,
DerivedData and local logs under:

```text
~/Library/Application Support/ios-one-command/<project-key>/
```

Set `IOS_ONE_HOME` to choose another state directory. The launcher does not patch
your `.pbxproj` or copy app source over existing work. Xcode itself may update
`Package.resolved`/workspace state, run build scripts, contact package repositories,
and create/update signing profiles or register a development device during
automatic provisioning. The selected app is installed and its existing process
is relaunched. Build only projects whose source and build scripts you trust.

There is no launcher telemetry, AI API call, secret-key export, or automatic log
upload. Raw local Xcode logs may contain identifying information. Use
`shareable-report.json` when reporting launcher failures; it is built from an
allowlist of status fields and excludes commands, paths, device names/IDs, Team
IDs, certificate output and raw error text.

The standalone installer verifies the embedded ZIP and source hashes. A repeated
install reuses identical files; it stops before overwriting edited source. It
does not merge or upgrade an existing installation in this preview. Hashes detect
corruption and version mismatches; they are not a publisher's digital signature.

## Verify and contribute

```bash
python3 -m unittest discover -s tests
bash Verify_On_Mac.command
python3 scripts/simulator_smoke.py
```

The first command checks orchestration with tool doubles plus real local process
and filesystem tests. The second builds the demo with Xcode for Simulator. The
third also installs and launches it in an available iPhone Simulator. Physical
device checks remain separate. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Scope and existing tools

[fastlane](https://docs.fastlane.tools/) already automates build and distribution
workflows. This project focuses on the small loop of getting a prepared iOS
project running locally, with guided setup and understandable failures. It uses
Apple's `xcodebuild`, `xcdevice`, `devicectl`, and `simctl` tools.

This preview does not submit apps to App Store Connect, perform TestFlight review,
install Xcode, manage Apple Account credentials, attach a debugger, generate
arbitrary app projects, or update existing app source packages. Custom build
output directories outside its DerivedData location are not yet supported.

[Publishing instructions](docs/publishing.md) · [Demo recording](docs/demo-recording.md)

MIT licensed. Developed by masaaki office with AI assistance.
