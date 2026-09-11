# Changelog

## 0.1.0-preview.1 — 2026-09-11

- Initial generic Xcode project/workspace launcher with device and Simulator paths.
- Japanese/English guidance, saved choices, private local logs and shareable reports.
- Existing signing settings preserved; explicit Team override and certificate OU fallback.
- Multi-bundle protection for bundle ID overrides; built product identity check.
- Process timeouts, cancellation cleanup and a per-project execution lock.
- HelloDevice SwiftUI demo, Python tests and a Mac Simulator CI workflow.
- Manifest-checked source distribution and standalone Mac launcher.
- Explicit new-repository publishing command; default invocation previews only.

Validation update, 2026-09-11: a user-supplied log and before/after screenshots
confirmed a HelloDevice build/install/launch and confirmation-button interaction
with Xcode 26.2 (17C52) and iOS 26.6.1 (23G83). Launcher and demo runtime sources
were kept unchanged for this documentation update. Python/process/filesystem
checks passed on Linux. Simulator, additional device environments and GitHub CI
remain pending.

Publication preflight correction, 2026-09-11: compare canonical workspace paths
in tests to account for macOS temporary-directory aliases; add a symlink-path
regression and capture expected test errors. Show publication test progress.
Launcher and demo runtime sources remain unchanged. All 57 tests passed on Linux;
the corrected Mac publication preflight awaits a rerun.

Public CI and release distribution update, 2026-09-11: the corrected Mac
publication preflight passed and the repository was published. Initial GitHub CI
passed on Python 3.9/3.13 (Linux) and 3.11 (macOS), including a HelloDevice
Simulator build/install/launch with Xcode 26.6 and iOS 26.5. Added versioned README
download links, standalone/ZIP checksums and preview publication after successful
CI and a redacted Gitleaks history scan. Existing releases and tags are preserved.
The launcher and demo runtime sources remain unchanged.

Commit identity update, 2026-09-11: prepare a fresh repository history using
`developer@example.invalid` and add a check for public author/committer email
addresses. Preserve the current source and remove links to obsolete history.
The app launcher and demo runtime sources remain unchanged.
