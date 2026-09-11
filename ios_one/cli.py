"""Xcode orchestration using only Python's standard library and Apple tools."""
import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import uuid

from . import __version__
from .signing import discover_certificates

LANG = "en"
TOOL_ROOT = Path(__file__).resolve().parents[1]


def tr(ja, en):
    return ja if LANG == "ja" else en


class OneError(Exception):
    def __init__(self, code, message, step=None):
        super().__init__(message)
        self.code, self.step = code, step


def fail(code, ja, en, step=None):
    raise OneError(code, tr(ja, en), step)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())
        temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def read_settings(path):
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise OneError("CONFIG", tr("保存設定を読めません：", "Cannot read saved settings: ") + str(path)) from exc
    allowed = {"schema", "scheme", "configuration", "target_id", "target_kind", "team", "bundle_id"}
    if not isinstance(data, dict) or type(data.get("schema")) is not int or data.get("schema") != 1 or set(data) - allowed:
        fail("CONFIG", "保存設定の形式が違います。設定ファイルを確認してください。", "Invalid saved settings schema.")
    if any(not isinstance(v, str) for k, v in data.items() if k != "schema"):
        fail("CONFIG", "保存設定の値が正しくありません。", "Invalid saved setting value.")
    if data.get("target_kind") not in {None, "device", "simulator"}:
        fail("CONFIG", "保存された端末の種類が不正です。", "Invalid saved target kind.")
    if data.get("team"):
        validate_team(data["team"])
    if data.get("bundle_id"):
        validate_bundle(data["bundle_id"])
    return data


def version(value):
    match = re.search(r"(\d+)(?:[.-](\d+))?(?:[.-](\d+))?", value)
    return tuple(int(p or 0) for p in match.groups()) if match else (0, 0, 0)


def command_json(output, expected):
    decoder = json.JSONDecoder()
    for match in re.finditer(r"(?m)^\s*([\[{])", output):
        try:
            result, _ = decoder.raw_decode(output[match.start(1):])
        except ValueError:
            continue
        if isinstance(result, expected):
            return result
    fail("TOOL_JSON", "XcodeのJSON出力を読めません。ローカルログを確認してください。",
         "Cannot parse Xcode JSON. Inspect the local step log.")


@dataclass(frozen=True)
class Target:
    identifier: str
    name: str
    os_version: str
    kind: str
    state: str = ""


def physical_targets(items):
    result = []
    for item in items:
        if not isinstance(item, dict):
            fail("TOOL_SCHEMA", "Xcodeの端末一覧の形式が変わっています。", "Unrecognized Xcode device-list schema.")
        if (item.get("available") is True and item.get("simulator") is False
                and item.get("platform") == "com.apple.platform.iphoneos"
                and item.get("identifier") and version(item.get("operatingSystemVersion", "")) >= (17, 0, 0)):
            result.append(Target(item["identifier"], item.get("name", "iOS device"),
                                 item.get("operatingSystemVersion", ""), "device"))
    return sorted(result, key=lambda item: (item.name, item.identifier))


def simulator_targets(data):
    result = []
    if not isinstance(data.get("devices", {}), dict):
        fail("TOOL_SCHEMA", "Simulator一覧の形式が変わっています。", "Unrecognized Simulator device-list schema.")
    for runtime, items in data.get("devices", {}).items():
        if ".iOS-" not in runtime:
            continue
        os_version = runtime.rsplit(".iOS-", 1)[1].replace("-", ".")
        if version(os_version) < (17, 0, 0):
            continue
        for item in items:
            if item.get("isAvailable") is True and item.get("udid"):
                result.append(Target(item["udid"], item.get("name", "iOS Simulator"),
                                     os_version, "simulator", item.get("state", "")))
    return sorted(result, key=lambda item: (item.state != "Booted", item.name, item.identifier))


def choose(items, title, label=str, no_input=False):
    if not items:
        raise OneError("NOT_FOUND", title + tr("が見つかりません。", " not found."))
    if len(items) == 1:
        return items[0]
    print(title, flush=True)
    for index, item in enumerate(items, 1):
        print("  %d. %s" % (index, label(item)), flush=True)
    if no_input or not sys.stdin.isatty():
        fail("AMBIGUOUS", "候補が複数あります。表示された名前・IDをオプションで指定してください。",
             "Multiple candidates. Select an explicit name or ID with the corresponding option.")
    while True:
        try:
            answer = input(tr("番号：", "Number: ")).strip()
        except EOFError as exc:
            raise OneError("INPUT", tr("選択を読み取れません。", "No selection received.")) from exc
        if answer.isdigit() and 1 <= int(answer) <= len(items):
            return items[int(answer) - 1]
        print(tr("一覧の番号を入力してください。", "Enter a number from the list."), flush=True)


def select_target(devices, simulators, saved, device=None, simulator=None, no_input=False):
    explicit = device is not None or simulator is not None
    if explicit:
        kind, requested = ("device", device) if device is not None else ("simulator", simulator)
    elif saved.get("target_id"):
        kind, requested = saved.get("target_kind"), saved["target_id"]
    else:
        kind, requested = "device", "auto"
    candidates = devices if kind == "device" else simulators
    if requested != "auto":
        candidates = [item for item in candidates if requested in {item.identifier, item.name}]
    if not candidates:
        fail("TARGET_UNAVAILABLE", "指定または保存された端末が使えません。接続・ロック解除を確認するか、--device / --simulator で選び直してください。",
             "Requested/saved target unavailable. Connect and unlock it, or select --device / --simulator explicitly.")
    if kind == "simulator" and requested == "auto":
        booted = [item for item in candidates if item.state == "Booted"]
        if len(booted) == 1:
            return booted[0]
    return choose(candidates, tr("実行先", "Destination"),
                  lambda t: "%s / iOS %s / %s" % (t.name, t.os_version, t.identifier), no_input)


def validate_team(team):
    if not re.fullmatch(r"[A-Z0-9]{10}", team):
        fail("TEAM", "Team IDは英大文字・数字の10桁で指定してください。", "Team ID must contain 10 uppercase letters/digits.")
    return team


def validate_bundle(bundle_id):
    if not re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", bundle_id):
        fail("BUNDLE_ID", "Bundle IDは英数字・ハイフンをピリオドで区切ってください。", "Use a reverse-domain bundle ID containing letters, digits, hyphens and periods.")
    return bundle_id


def resolve_container(requested, no_input=False, cwd=None):
    root = Path(cwd or Path.cwd())
    if requested:
        path = Path(requested).expanduser().resolve()
        if path.suffix not in {".xcodeproj", ".xcworkspace"} or not path.is_dir():
            fail("PROJECT", "--projectに.xcodeproj / .xcworkspaceフォルダを指定してください。",
                 "--project must point to an existing .xcodeproj or .xcworkspace directory.")
        return path
    # Only immediate children: never guess between unrelated projects in a tree.
    workspaces = sorted(p for p in root.glob("*.xcworkspace") if p.is_dir())
    projects = sorted(p for p in root.glob("*.xcodeproj") if p.is_dir())
    return choose(workspaces or projects, tr("Xcodeプロジェクト", "Xcode project"),
                  lambda p: p.name, no_input).resolve()


def select_app(rows, requested=None, no_input=False):
    if any(not isinstance(row, dict) or not isinstance(row.get("buildSettings", {}), dict) for row in rows):
        fail("TOOL_SCHEMA", "Xcodeのビルド設定の形式が変わっています。", "Unrecognized Xcode build-settings schema.")
    apps = [row for row in rows if row.get("buildSettings", {}).get("PRODUCT_TYPE") == "com.apple.product-type.application"]
    if requested:
        apps = [row for row in apps if row.get("target") == requested]
    return choose(apps, tr("起動するアプリ（--app-target）", "App to launch (--app-target)"),
                  lambda row: row.get("target", "?"), no_input)


def bundle_override_allowed(rows, app):
    # A command-line PRODUCT_BUNDLE_IDENTIFIER applies to every target in the scheme.
    # Refuse if another bundle could receive the same ID (extensions, frameworks, tests).
    for row in rows:
        settings = row.get("buildSettings", {})
        if row is not app and (settings.get("WRAPPER_EXTENSION") or settings.get("PRODUCT_BUNDLE_IDENTIFIER")):
            return False
    return True


def select_team(explicit, project_team, saved_team, certificates, no_input=False):
    if explicit:
        return validate_team(explicit)
    if project_team and not project_team.startswith("$("):
        return validate_team(project_team)
    if saved_team:
        return validate_team(saved_team)
    teams = sorted({item.team_id for item in certificates})
    if not teams:
        fail("SIGNING_SETUP", "Xcode → Settings → Accountsでログインし、Signing & CapabilitiesでTeamを選んで再実行してください。--teamでも指定できます。",
             "Sign in under Xcode Settings > Accounts, select a Team in Signing & Capabilities, and retry. You can also pass --team.")
    return choose(teams, tr("署名Team（--team）", "Signing Team (--team)"), no_input=no_input)


def failure_hint(step, output):
    text = output.lower()
    if "no account for team" in text or "authentication" in text:
        return tr("XcodeのAccountsで該当Teamへのログイン状態を確認してください。", "Check the account for this Team under Xcode Settings > Accounts.")
    if "developer mode" in text:
        return tr("iPhone/iPadの設定 → プライバシーとセキュリティ → デベロッパモードを確認してください。", "Check Settings > Privacy & Security > Developer Mode on the device.")
    if "locked" in text or "passcode" in text:
        return tr("端末をロック解除し、Macを信頼してから再実行してください。", "Unlock the device, trust this Mac, and retry.")
    if "provision" in text or "signing" in text or "certificate" in text:
        return tr("XcodeのTeam・Bundle ID・署名証明書を確認してください。詳細は工程ログにあります。", "Check the Xcode Team, bundle ID and signing identity. Details are in the step log.")
    return {
        "xcode-first-launch": tr("Xcodeを一度開き、初回設定を完了してください。", "Open Xcode and finish first-launch setup."),
        "resolve-packages": tr("通信と依存パッケージの取得権限を確認してください。", "Check connectivity and access to package repositories."),
        "build": tr("buildログ内の最初のコンパイルエラーを確認してください。", "Inspect the first compiler error in the build log."),
        "install": tr("端末の接続・ロック解除・署名設定を確認してください。", "Check the device connection, unlock state and signing settings."),
        "launch": tr("端末のロック解除とデベロッパモードを確認してください。", "Unlock the device and check Developer Mode."),
    }.get(step, tr("ローカルの工程ログを確認してください。", "Inspect the local step log."))


def stop_process(process):
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()


class Runner:
    def __init__(self, root, state, env=None, timeout=1800, heartbeat=15):
        self.root, self.state = root, state
        self.env = dict(os.environ if env is None else env)
        self.timeout, self.heartbeat = timeout, heartbeat
        self.logs = state / "logs" / (datetime.now().strftime("%Y%m%d-%H%M%S-%f") + "-" + str(os.getpid()))
        self.logs.mkdir(parents=True, mode=0o700)
        self.steps = []
        self.summary = {"schema": 1, "tool_version": __version__, "host_os": platform.system()}

    def run(self, arguments, label, check=True, timeout=None):
        arguments = [str(item) for item in arguments]
        log = self.logs / ("%02d-%s.log" % (len(self.steps) + 1, re.sub(r"[^A-Za-z0-9_-]", "_", label)))
        step = {"step": label, "command": shlex.join(arguments), "log": str(log)}
        self.steps.append(step)
        print("› " + label + " …", flush=True)
        started, process = time.monotonic(), None
        deadline = started + (self.timeout if timeout is None else timeout)
        try:
            with log.open("w", encoding="utf-8") as output:
                log.chmod(0o600)
                process = subprocess.Popen(arguments, cwd=self.root, env=self.env, stdout=output,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(arguments, time.monotonic() - started)
                    try:
                        code = process.wait(timeout=min(self.heartbeat, remaining))
                        break
                    except subprocess.TimeoutExpired:
                        print("  %s … %ds" % (label, time.monotonic() - started), flush=True)
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            if process is not None:
                stop_process(process)
            step["exit_code"] = process.returncode if process is not None else None
            step["duration_seconds"] = round(time.monotonic() - started, 2)
            if isinstance(exc, KeyboardInterrupt):
                raise
            raise OneError("TIMEOUT", label + tr("がタイムアウトしました。再実行できます。", " timed out. You can retry."), label) from exc
        except OSError as exc:
            step["exit_code"] = None
            raise OneError("COMMAND", label + ": " + str(exc), label) from exc
        step.update(exit_code=code, duration_seconds=round(time.monotonic() - started, 2))
        output = log.read_text(encoding="utf-8", errors="replace")
        if code and check:
            tail = "\n".join(output.splitlines()[-14:])
            raise OneError("STEP_FAILED", label + "\n" + tail + "\n" + failure_hint(label, output), label)
        return output

    def finish(self, status, code=None):
        self.summary.update(status=status, error_code=code)
        write_json(self.logs / "result.json", {**self.summary, "steps": self.steps})
        # Construct from a whitelist: no raw log, command, path, ID, Team or device name.
        public = {key: self.summary[key] for key in (
            "schema", "tool_version", "host_os", "xcode_version", "command", "target_kind",
            "ios_version", "status", "error_code", "build", "install", "launch") if key in self.summary}
        public["steps"] = [{key: step.get(key) for key in ("step", "exit_code", "duration_seconds")}
                           for step in self.steps if not step["step"].startswith("signing-")]
        write_json(self.logs / "shareable-report.json", public)
        write_json(self.state / "latest-report.json", public)
        print(tr("ローカルログ：", "Local logs: ") + str(self.logs), flush=True)


def state_root(container=None):
    home = Path(os.environ.get("IOS_ONE_HOME", str(Path.home() / "Library/Application Support/ios-one-command"))).expanduser().resolve()
    identity = str(container) if container else "doctor"
    key = hashlib.sha256(identity.encode()).hexdigest()[:20]
    state = home / key
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    return state


@contextmanager
def project_lock(state):
    import fcntl
    with (state / "run.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise OneError("BUSY", tr("このプロジェクトの別の処理が実行中です。完了後に再実行してください。", "Another run is using this project. Retry when it finishes.")) from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def configure_xcode(runner, selected=None):
    specified = selected or runner.env.get("DEVELOPER_DIR")
    if specified:
        candidate = Path(specified).expanduser()
        candidates = [candidate / "Contents/Developer" if candidate.suffix == ".app" else candidate]
    else:
        active = runner.run(["/usr/bin/xcode-select", "-p"], "xcode-location", check=False, timeout=20).strip()
        candidates = ([Path(active)] if active else []) + [Path("/Applications/Xcode.app/Contents/Developer")]
    chosen = next((p for p in candidates if (p / "usr/bin/xcodebuild").is_file()), None)
    if chosen is None:
        fail("XCODE", "Xcode 15以降をインストールして一度開いてください。Command Line Toolsのみでは動きません。",
             "Install and open full Xcode 15+. Command Line Tools alone are insufficient.")
    runner.env["DEVELOPER_DIR"] = str(chosen.resolve())
    text = runner.run(["/usr/bin/xcodebuild", "-version"], "xcode-version", timeout=30)
    match = re.search(r"Xcode\s+(\d+(?:\.\d+)*)", text)
    if not match or version(match.group(1)) < (15, 0, 0):
        fail("XCODE_VERSION", "Xcode 15以降が必要です。--xcodeで選び直せます。", "Xcode 15+ is required. Select a toolchain with --xcode.")
    runner.summary["xcode_version"] = match.group(1)
    runner.run(["/usr/bin/xcodebuild", "-checkFirstLaunchStatus"], "xcode-first-launch", timeout=30)
    runner.run(["/usr/bin/xcrun", "--find", "devicectl"], "device-tools", timeout=30)
    print(text.strip(), flush=True)


def list_devices(runner, kind):
    if kind == "device":
        return physical_targets(command_json(runner.run(
            ["/usr/bin/xcrun", "xcdevice", "list", "--timeout", "5"], "list-devices", timeout=60), list))
    return simulator_targets(command_json(runner.run(
        ["/usr/bin/xcrun", "simctl", "list", "devices", "available", "-j"], "list-simulators", timeout=60), dict))


def build_arguments(container, scheme, configuration, destination, state):
    flag = "-workspace" if container.suffix == ".xcworkspace" else "-project"
    return ["/usr/bin/xcodebuild", flag, str(container), "-scheme", scheme,
            "-configuration", configuration, "-destination", destination, "-destination-timeout", "30",
            "-derivedDataPath", str(state / "DerivedData"), "-clonedSourcePackagesDirPath", str(state / "SourcePackages")]


def verify_product(settings, state, expected_bundle):
    folder, name = settings.get("TARGET_BUILD_DIR"), settings.get("FULL_PRODUCT_NAME")
    if not folder or not name or Path(name).name != name or not name.endswith(".app"):
        fail("PRODUCT", "ビルドされた.appの場所を確認できません。", "Cannot resolve the built .app product.")
    app = (Path(folder) / name).resolve()
    if not app.is_relative_to((state / "DerivedData").resolve()):
        fail("PRODUCT_PATH", "独自のビルド出力先は未対応です。DerivedData内の出力を使用してください。", "Custom build output paths are not supported; use the configured DerivedData directory.")
    try:
        with (app / "Info.plist").open("rb") as stream:
            info = plistlib.load(stream)
    except (OSError, ValueError, plistlib.InvalidFileException) as exc:
        raise OneError("PRODUCT", tr("ビルド済みInfo.plistを読めません。", "Cannot read the built Info.plist.")) from exc
    if info.get("CFBundleIdentifier") != expected_bundle or info.get("CFBundlePackageType") != "APPL":
        fail("PRODUCT_ID", "ビルド済みアプリのIDが設定と一致しません。", "Built app identity does not match the selected settings.")
    executable = info.get("CFBundleExecutable", "")
    if not executable or Path(executable).name != executable or not (app / executable).is_file():
        fail("PRODUCT", "アプリの実行ファイルが見つかりません。", "Built app executable is missing.")
    return app


def install_and_launch(runner, target, app, bundle_id, app_args):
    if target.kind == "device":
        runner.run(["/usr/bin/xcrun", "devicectl", "device", "install", "app", "--device", target.identifier, app], "install", timeout=300)
        runner.summary["install"] = "passed"
        runner.summary["launch"] = "running"
        runner.run(["/usr/bin/xcrun", "devicectl", "device", "process", "launch", "--device", target.identifier,
                    "--terminate-existing", bundle_id, "--", *app_args], "launch", timeout=120)
    else:
        if target.state != "Booted":
            runner.run(["/usr/bin/xcrun", "simctl", "boot", target.identifier], "boot-simulator", timeout=120)
        runner.run(["/usr/bin/xcrun", "simctl", "bootstatus", target.identifier, "-b"], "wait-simulator", timeout=600)
        simulator = Path(runner.env["DEVELOPER_DIR"]) / "Applications/Simulator.app"
        runner.run(["/usr/bin/open", "-a", simulator, "--args", "-CurrentDeviceUDID", target.identifier], "open-simulator", timeout=30)
        runner.run(["/usr/bin/xcrun", "simctl", "install", target.identifier, app], "install", timeout=120)
        runner.summary["install"] = "passed"
        runner.summary["launch"] = "running"
        runner.run(["/usr/bin/xcrun", "simctl", "launch", "--terminate-running-process", target.identifier, bundle_id, *app_args], "launch", timeout=120)
    runner.summary["launch"] = "passed"


def workflow(args, runner, container):
    runner.summary["command"] = args.command
    configure_xcode(runner, args.xcode)
    if args.command == "doctor":
        for kind in ("device", "simulator"):
            targets = list_devices(runner, kind)
            print("%s: %d" % (kind, len(targets)), flush=True)
            for target in targets:
                print("  %s / iOS %s / %s" % (target.name, target.os_version, target.identifier), flush=True)
        certificates = discover_certificates(runner)
        print(tr("証明書OUのTeam：", "Certificate OU Teams: ") + ", ".join(sorted({c.team_id for c in certificates})), flush=True)
        print(tr("環境確認が完了しました。アプリのビルドは別途検証します。", "Environment inspection complete. App builds require separate verification."), flush=True)
        return
    saved = read_settings(runner.state / "settings.json")
    flag = "-workspace" if container.suffix == ".xcworkspace" else "-project"
    listing = command_json(runner.run(["/usr/bin/xcodebuild", flag, container, "-list", "-json"], "list-schemes"), dict)
    schemes = listing.get("workspace", listing.get("project", {})).get("schemes", [])
    selected = args.scheme or saved.get("scheme")
    if selected and selected not in schemes:
        fail("SCHEME", "指定・保存されたSchemeがありません。XcodeでSchemeを共有するか--schemeで選び直してください。",
             "Requested/saved scheme missing. Share it in Xcode or select --scheme explicitly.")
    scheme = selected or choose(schemes, "Scheme (--scheme)", no_input=args.no_input)
    if saved.get("scheme") != scheme or saved.get("configuration") != args.configuration:
        saved = {}
    target = None
    if args.command != "verify":
        kind = "device" if args.device is not None else "simulator" if args.simulator is not None else saved.get("target_kind", "device")
        targets = list_devices(runner, kind)
        target = select_target(targets if kind == "device" else [], targets if kind == "simulator" else [], saved,
                               args.device, args.simulator, args.no_input)
        runner.summary.update(target_kind=target.kind, ios_version=target.os_version)
        print(tr("実行先：", "Destination: ") + target.name + " / " + target.os_version, flush=True)
    else:
        runner.summary["target_kind"] = "generic-simulator"
    destination = "id=" + target.identifier if target else "generic/platform=iOS Simulator"
    base = build_arguments(container, scheme, args.configuration, destination, runner.state)
    runner.run(base + ["-resolvePackageDependencies"], "resolve-packages")
    rows = command_json(runner.run(base + ["-disableAutomaticPackageResolution", "-showBuildSettings", "-json"], "build-settings"), list)
    app_row = select_app(rows, args.app_target, args.no_input)
    settings = app_row["buildSettings"]
    overrides = []
    bundle_id = args.bundle_id or saved.get("bundle_id")
    if args.command == "demo" and not bundle_id:
        bundle_id = "dev.iosone.hello.demo" + uuid.uuid4().hex[:12]
    if bundle_id:
        validate_bundle(bundle_id)
        if not bundle_override_allowed(rows, app_row):
            fail("MULTI_BUNDLE", "複数のBundleを持つSchemeでは--bundle-idを使えません。Xcodeで各ターゲットのIDを設定してください。",
                 "--bundle-id is not supported for schemes with multiple bundles. Configure each target's ID in Xcode.")
        overrides.append("PRODUCT_BUNDLE_IDENTIFIER=" + bundle_id)
    expected_bundle = bundle_id or settings.get("PRODUCT_BUNDLE_IDENTIFIER", "")
    validate_bundle(expected_bundle)
    if target and version(target.os_version) < version(settings.get("IPHONEOS_DEPLOYMENT_TARGET", "0")):
        fail("IOS_VERSION", "端末のiOSがアプリの最低対応バージョンより古いです。別の端末を選んでください。",
             "The selected device is older than the app's deployment target. Select another device.")
    team = None
    if target and target.kind == "device":
        project_team = settings.get("DEVELOPMENT_TEAM", "")
        if not args.team and (settings.get("CODE_SIGN_STYLE") == "Manual" or project_team):
            # Preserve manual signing. Xcode validates its profiles and identity.
            print(tr("プロジェクトの署名設定を使用します。", "Using the project's signing settings."), flush=True)
        else:
            if not args.team and not bundle_override_allowed(rows, app_row):
                fail("MULTI_TEAM", "複数Bundleの署名はXcodeで設定してください。Teamを一括指定する場合は--teamを使用します。",
                     "Configure multi-bundle signing in Xcode, or explicitly use --team to override the whole scheme.")
            certs = [] if args.team or project_team or saved.get("team") else discover_certificates(runner)
            team = select_team(args.team, project_team, saved.get("team"), certs, args.no_input)
            overrides += ["CODE_SIGN_STYLE=Automatic", "DEVELOPMENT_TEAM=" + team]
        if settings.get("CODE_SIGN_STYLE") != "Manual" or args.team:
            overrides += ["-allowProvisioningUpdates", "-allowProvisioningDeviceRegistration"]
    else:
        overrides.append("CODE_SIGNING_ALLOWED=NO")
    if bundle_id or team:
        final_rows = command_json(runner.run(base + overrides + ["-disableAutomaticPackageResolution", "-showBuildSettings", "-json"], "effective-settings"), list)
        settings = select_app(final_rows, app_row["target"], True)["buildSettings"]
        if settings.get("PRODUCT_BUNDLE_IDENTIFIER") != expected_bundle:
            fail("BUNDLE_ID", "Bundle IDの適用結果を確認できません。", "Effective bundle ID did not match the requested ID.")
    updated = {"schema": 1, "scheme": scheme, "configuration": args.configuration}
    if target:
        updated.update(target_id=target.identifier, target_kind=target.kind)
    else:
        updated.update({k: saved[k] for k in ("target_id", "target_kind") if k in saved})
    if team or saved.get("team"):
        updated["team"] = team or saved["team"]
    if bundle_id:
        updated["bundle_id"] = bundle_id
    write_json(runner.state / "settings.json", updated)
    runner.summary["build"] = "running"
    runner.run(base + overrides + ["-disableAutomaticPackageResolution", "-resultBundlePath", runner.logs / "build.xcresult", "build"], "build")
    runner.summary["build"] = "passed"
    app = verify_product(settings, runner.state, expected_bundle)
    if target:
        runner.summary["install"] = "running"
        install_and_launch(runner, target, app, expected_bundle, args.app_args)
        print(tr("起動コマンドが成功しました。端末の画面を確認してください。", "Launch command succeeded. Check the app on your device."), flush=True)
    else:
        print(tr("Simulator向けビルドが成功しました。実機動作は別途確認してください。", "Simulator build passed. Physical-device behavior needs separate verification."), flush=True)


def parse_args(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    app_args = []
    if "--" in argv:
        boundary = argv.index("--")
        argv, app_args = argv[:boundary], argv[boundary + 1:]
    parser = argparse.ArgumentParser(prog="ios-one", description="Build, install and launch iOS apps. / iOSアプリを実機まで一括起動")
    parser.add_argument("command", nargs="?", choices=["run", "demo", "doctor", "verify", "report"], default="run")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--project", help=".xcodeproj or .xcworkspace path / プロジェクトの場所")
    parser.add_argument("--scheme", help="shared scheme / 共有Scheme")
    parser.add_argument("--app-target", help="app target if the scheme builds multiple apps / 起動ターゲット")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--device", nargs="?", const="auto", help="iPhone/iPad ID or exact name / 実機")
    group.add_argument("--simulator", nargs="?", const="auto", help="Simulator ID or exact name")
    parser.add_argument("--team", help="10-character Apple Team ID")
    parser.add_argument("--bundle-id", help="single-bundle schemes only / 複数BundleのSchemeでは使用不可")
    parser.add_argument("--configuration", default="Debug")
    parser.add_argument("--xcode", help="Xcode.app or Contents/Developer")
    parser.add_argument("--no-input", action="store_true", help="fail on ambiguity / 曖昧な選択では停止")
    parser.add_argument("--lang", choices=["ja", "en"], default="ja" if os.environ.get("LANG", "").startswith("ja") else "en")
    parser.add_argument("--timeout", type=int, default=1800, help="build/package step timeout in seconds")
    parser.add_argument("--output", help="new file for a shareable report / 共有用レポートの新規出力先")
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.command in {"verify", "doctor", "report"} and (args.device is not None or args.simulator is not None or app_args):
        parser.error("--device, --simulator and app arguments apply only to run/demo")
    if args.command == "demo" and (args.project or args.scheme or args.app_target):
        parser.error("demo uses the bundled HelloDevice project")
    args.app_args = app_args
    return args


def main(argv=None):
    global LANG
    args = parse_args(argv)
    LANG = args.lang
    runner = None
    try:
        if args.command != "report" and platform.system() != "Darwin":
            fail("PLATFORM", "実行にはXcodeのあるMacが必要です。", "Running iOS apps requires a Mac with Xcode.")
        if args.team:
            validate_team(args.team)
        if args.bundle_id:
            validate_bundle(args.bundle_id)
        if args.command == "demo":
            container = TOOL_ROOT / "examples/HelloDevice/HelloDevice.xcodeproj"
            args.scheme = "HelloDevice"
        elif args.command == "doctor" and not args.project:
            container = None
        else:
            container = resolve_container(args.project, args.no_input)
        os.umask(0o077)
        state = state_root(container)
        if args.command == "report":
            report = state / "latest-report.json"
            if not report.is_file():
                fail("REPORT", "このプロジェクトのレポートはまだありません。", "No report exists for this project yet.")
            if args.output:
                output = Path(args.output).expanduser()
                with output.open("x", encoding="utf-8") as stream:
                    stream.write(report.read_text(encoding="utf-8"))
                print(str(output.resolve()))
            else:
                print(report.read_text(encoding="utf-8"), end="")
            return 0
        with project_lock(state):
            runner = Runner(container.parent if container else Path.cwd(), state, timeout=args.timeout)
            try:
                workflow(args, runner, container)
            except BaseException:
                for key in ("build", "install", "launch"):
                    if runner.summary.get(key) == "running":
                        runner.summary[key] = "failed"
                raise
            runner.finish("passed")
        return 0
    except KeyboardInterrupt:
        print(tr("\n中断しました。同じコマンドで再実行できます。", "\nCancelled. You can rerun the same command."), file=sys.stderr)
        if runner:
            runner.finish("cancelled", "CANCELLED")
        return 130
    except (OneError, OSError, ValueError) as exc:
        code = getattr(exc, "code", "IO")
        print("\n[%s] %s" % (code, exc), file=sys.stderr, flush=True)
        if runner:
            runner.finish("failed", code)
        return 2


if __name__ == "__main__":
    sys.exit(main())
