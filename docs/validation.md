# Validation record

Version: **0.1.0-preview.1**. Prepared on **2026-09-11**.

Automated result: **70 tests passed** on Linux with **Python 3.12.14**.
All Python sources also passed a Python 3.9 grammar check. That is a syntax
check, not a claim that the complete suite ran under Python 3.9 locally.

| Check | Status | Evidence / remaining work |
| --- | --- | --- |
| Python orchestration, selection and signing logic | PASS on Linux | Standard-library unittest suite |
| Real local subprocess exit/timeout/argument handling | PASS on Linux | Tests execute child Python processes |
| Source install/reinstall/conflict and archive validation | PASS on Linux | Temporary filesystem tests |
| Canonical project paths through directory symlinks | PASS on Linux | Regression test covers automatic and explicit workspace selection |
| Python syntax and launcher shell syntax | PASS on Linux | compileall and bash syntax checks |
| Xcode device build | PASS — user-supplied run log | Xcode 26.2 (17C52), HelloDevice |
| Generic Simulator build | PENDING | Run `bash Verify_On_Mac.command` |
| Actual Simulator build, install and launch | PASS — GitHub Actions | Xcode 26.6 (17F113), iPhone 17 Simulator, iOS 26.5; no UI interaction assertion |
| Physical iPhone install and launch | PASS — user-supplied log and screenshots | iOS 26.6.1 (23G83), one reported environment |
| Visible UI and confirmation button | PASS — before/after screenshots | Initial phone icon changes to a green check; text and button state change |
| Physical iPad | PENDING | No iPad evidence supplied |
| Existing third-party project | PENDING | Verify one simple app and one prepared workspace |
| Second developer's Mac | PENDING | Collect a separate reproduction report |
| Headless Simulator control flow and failure propagation | PASS on Linux | Boot/install/launch scenarios; no Xcode execution claim |
| GitHub Actions | Corrected smoke PENDING | New public history passed 63 tests on three Python versions and email/Gitleaks checks; Simulator GUI timed out. See the run below |
| Publication preflight on the Mac | PASS — user-supplied terminal result | Corrected pre-publication tests passed before the initial push |
| Public repository creation | PASS | Public repository and initial source tree verified |

Tests using a tool double confirm control flow and failure handling. They do not
validate Apple's command output on a real Mac, code signing, Swift compilation,
device compatibility or the visible app UI. The physical-device rows above rely
on separate user-supplied evidence for this exact preview, not on the tool doubles
or prior app-specific launchers. This is a smoke test of one reported environment,
not a compatibility claim covering every Xcode/iOS combination.

## Publication preflight correction

The first Mac publication attempt ran 56 tests and stopped on one assertion:
the CLI correctly resolved a temporary workspace path through `/var` to
`/private/var`, while the test expected the unresolved path. The test now compares
canonical paths. An additional directory-symlink regression covers this behavior
on Linux as well. Expected error messages from negative tests are captured so
they cannot be confused with live publication failures.

The launcher and demo runtime sources are unchanged. The corrected suite passed
on Linux and then passed the user's Mac publication preflight. The failed
preflight created no repository; the later successful run published this preview.

## Public CI record

Before repository reinitialization, the initial Verify run completed successfully
on 2026-09-11. All 57 tests passed in each Python job
(Linux 3.9/3.13, macOS 3.11).
The Mac job also built, installed and launched HelloDevice with Xcode 26.6
(17F113), on the iPhone 17 Simulator running iOS 26.5.
This confirms the automated launch path; it does not verify Simulator pixels,
touch interaction, physical-device signing or other projects.

A subsequent run passed all 63 tests on those three Python versions and passed
the Gitleaks history scan. Its Simulator build completed, but opening the
Simulator GUI exceeded its timeout, so the release job did not run.
These are summaries of logs reviewed before reinitialization; the old Actions
runs are not retained as live links. Check the current
[Actions page](https://github.com/masaakisakamoto/ios-one-command/actions)
for results from the new repository history.

Subsequent release publication requires the current commit's Python tests,
Simulator smoke and Gitleaks history scan to pass. The release's Git tag records
the exact source commit. Historical results above do not establish that the
new repository's current commit has passed; new runs provide that evidence.

## Simulator CI correction after republication

[Verify run 34612379265](https://github.com/masaakisakamoto/ios-one-command/actions/runs/34612379265)
tested the new root commit `4801bc0c83e01bec8293fcdfe9b5c7ee27778c44`.
All 63 tests passed on Python 3.9/3.13 (Linux) and 3.11 (macOS), as did public
commit-email checks and the Gitleaks history scan. Xcode 26.6 built the demo,
and the iPhone 17 / iOS 26.5 Simulator finished booting. Opening the Simulator
window exceeded the 30-second timeout, so install/launch and release did not run.

The corrected smoke requests `--headless`: it still builds, boots, installs and
launches through the normal CLI, without requiring a Simulator window. Seven
regression tests cover option scope, normal window behavior, command order and
failure propagation. The resulting 70-test suite passed on Linux. A new Mac CI
run is required to validate this corrected smoke before publishing release assets.

## Mac acceptance record

Updated from the run log and two screenshots supplied on 2026-09-11.

| Field | Result |
| --- | --- |
| Date | 2026-09-11 |
| Mac / macOS | Mac used; exact hardware/macOS not captured in this run log |
| Xcode version | 26.2, build 17C52 |
| Python version on the Mac | Not captured |
| iPhone or iPad model / OS | iPhone, exact model not captured; iOS 26.6.1 (23G83) as reported by the tool |
| Demo installed and launched | Passed in the run log; initial app screen supplied |
| Button works | After-tap screenshot shows green check, “You're up and running.” and “Try again” |
| Second run reuses choices and bundle identity | Not yet observed on the device |
| Existing project / workspace works | Not yet observed |
| Project source diff after run | Not supplied |
| Shareable report | JSON not supplied; terminal text and two screenshots reviewed |

For first-use testing, include a run with the device locked/disconnected and
confirm that retry succeeds after following the guidance. These are targeted
checks of the setup experience, not a requirement to repeat unrelated app tests.

The public record contains this summary only. It omits the raw log's local paths,
device nickname and certificate handle. Screenshots were used for review and are
not embedded in the public source distribution.

日本語：Linuxの自動テストに加え、提供されたログと操作前後の画像から、
１環境でのiPhone実機起動・画面表示・ボタン操作を確認しました。
GitHub CIでも自動テストとSimulator起動が成功しました。
別の開発者のMac・実機iPad・既存の別プロジェクトは、引き続き未確認です。
