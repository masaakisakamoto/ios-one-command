# Publish a new GitHub repository / GitHub公開

The source set is prepared for the repository name `ios-one-command`, with the
description in `scripts/publish.py`. The repository is not created by installing
or trying the demo.

## 1. Check the recorded validation scope

The provided log and screenshots already confirm the included app's build,
installation, launch and button interaction on one iPhone environment with
Xcode 26.2 and iOS 26.6.1. See `docs/validation.md`. Repeating this successful
device check is not required just to publish the preview.

For additional Mac/Simulator verification, the following commands are available:

```bash
bash Verify_On_Mac.command
bash Try_Demo.command --lang ja
```

Record additional checks in `docs/validation.md` as they actually occur. Existing
projects, Simulator and other developer environments remain follow-up work.
The preview can be published with this measured scope clearly stated; do not
promote it to a broadly verified stable release on the basis of one smoke test.

## 2. Prepare GitHub CLI

The publication helper needs Git and the [GitHub CLI](https://cli.github.com/).
Authenticate with `gh auth login`. Configure your intended Git author name and
email before publishing. The helper does not invent your author identity or ask
you to paste a token into the project.

## 3. Review the publication target

```bash
bash Publish_GitHub.command
```

This displays a preview and validates file hashes. It does not create or push
a repository. `--owner ACCOUNT` and `--name NAME` can change the target.
If omitted, the actual publish uses the signed-in GitHub user's personal account.

## 4. Create and push the public preview

```bash
bash Publish_GitHub.command --public
```

This command **creates a new public GitHub repository and uploads the reviewed
source**. It runs the Python tests, copies only `public-files.json`'s file list
into a new local Git working copy, makes an initial commit, and invokes
[`gh repo create --public --source … --push`](https://cli.github.com/manual/gh_repo_create).
The resulting repository URL and local Git working-copy path are printed.

The copied source includes the MIT license, documentation, example, tests and CI.
Unlisted files, local build logs, Apple credentials, installed app state, existing
app code and previous repository history are not included. Source hash validation
is a version/content check; it is not a general secret scanner. Inspect any new
files you intentionally add to a future public source list.

If the target already exists, the helper stops. It does not change an existing
repository's visibility, merge another project, or force-push. If creation works
but upload fails, it retains the prepared Git copy and prints recovery guidance.

After publication, inspect the Actions tab. A supplied workflow is not evidence
that CI passed; wait for the actual Python and Mac Simulator jobs to complete.

## After editing this preview

Review your changes and refresh the manifest/distribution before using the helper:

```bash
python3 scripts/package_release.py
```

For later releases, work in the Git copy printed by the publishing command and
use normal commits and PRs. The new-repository helper is intentionally limited to
initial publication. Do not run it as an updater.

## Preview releases from the existing repository

On `masaakisakamoto/ios-one-command`, a push to `main` (or a manual Verify run on
`main`) publishes an unpublished preview version after the Python, Mac Simulator
and Gitleaks history jobs pass. Pull requests and forks do not publish releases.
Only the release job has repository-content write permission. It uses GitHub's
short-lived workflow token; no personal token belongs in the source.

The package contains the standalone `IOS_One_Command_Start.command`, the reviewed
source ZIP and `SHA256SUMS`. The publisher creates a draft at the tested commit,
checks the uploaded asset names and SHA-256 digests, then publishes a prerelease.
It never replaces a published release or moves an existing tag. An existing
draft stops publication so the maintainer can inspect a partial upload first.

For a new version, update `ios_one/__init__.py`, the README download links and
`CHANGELOG.md`, and add `docs/releases/<version>.md`. Run the tests and
`python3 scripts/package_release.py`, then commit the refreshed
`public-files.json` with those changes. A README-only change with an already
published version keeps that release intact. These previews are not marked as
the latest stable release; link to their explicit versioned URLs.

Git commits also publish the configured author name and email, independently of
the source-file allowlist. To avoid publishing a personal email in future
commits, use the exact GitHub-provided `noreply` address shown in your account's
email settings, following [GitHub's commit-email instructions](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address).
Changing this setting does not remove identity information from existing commits.

For this repository, the maintainer uses `developer@example.invalid` for both
Git author and committer email. GitHub noreply identities are also accepted.
The history check rejects other addresses without printing them into CI logs.
Use the fresh working copy after a repository reinitialization; do not merge
or push branches from an older copy containing the previous history.

日本語：今回の実機ログと画面で、サンプルの起動・表示・操作を確認済みです。
`Publish_GitHub.command`で公開対象を表示します。
`--public`付きで実行すると、新しいPublicリポジトリを作成してソースをアップロードします。
既存リポジトリは変更しません。GitHub CLIのログインとGitの著者設定が必要です。
