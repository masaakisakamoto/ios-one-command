import contextlib
import io
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ios_one import cli
from ios_one.signing import SigningCertificate, certificate_subject, development_identities


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.a = cli.Target("DEVICE-A", "My iPhone", "18.0", "device")
        self.b = cli.Target("DEVICE-B", "My iPhone", "18.0", "device")
        self.sim = cli.Target("SIM-A", "iPhone Simulator", "18.0", "simulator", "Booted")

    def test_physical_filter_excludes_unavailable_simulators_and_old_os(self):
        good = dict(available=True, simulator=False, platform="com.apple.platform.iphoneos", identifier="A", operatingSystemVersion="17.4", name="iPad")
        rows = [good, {**good, "available": False}, {**good, "simulator": True}, {**good, "operatingSystemVersion": "16.6"}, {**good, "platform": "com.apple.platform.appletvos"}]
        self.assertEqual([t.identifier for t in cli.physical_targets(rows)], ["A"])

    def test_simulator_filter_ignores_tv_and_unavailable(self):
        data = {"devices": {"com.apple.CoreSimulator.SimRuntime.iOS-17-5": [dict(udid="S", name="iPad", isAvailable=True), dict(udid="X", isAvailable=False)], "com.apple.CoreSimulator.SimRuntime.tvOS-18-0": [dict(udid="TV", isAvailable=True)]}}
        self.assertEqual([t.identifier for t in cli.simulator_targets(data)], ["S"])

    def test_default_does_not_silently_fall_back_to_simulator(self):
        with self.assertRaises(cli.OneError):
            cli.select_target([], [self.sim], {}, no_input=True)

    def test_explicit_simulator(self):
        self.assertEqual(cli.select_target([self.a], [self.sim], {}, simulator="auto", no_input=True), self.sim)

    def test_saved_unavailable_device_does_not_pick_another(self):
        with self.assertRaises(cli.OneError):
            cli.select_target([self.b], [], {"target_kind": "device", "target_id": "DEVICE-A"}, no_input=True)

    def test_explicit_selection_overrides_stale_saved_target(self):
        self.assertEqual(cli.select_target([self.b], [], {"target_kind": "device", "target_id": "OLD"}, device="DEVICE-B", no_input=True), self.b)

    def test_duplicate_device_names_require_id(self):
        with self.assertRaises(cli.OneError):
            cli.select_target([self.a, self.b], [], {}, device="My iPhone", no_input=True)

    def test_two_booted_simulators_remain_ambiguous(self):
        second = cli.Target("SIM-B", "Other", "18.0", "simulator", "Booted")
        with self.assertRaises(cli.OneError):
            cli.select_target([], [self.sim, second], {}, simulator="auto", no_input=True)

    def test_exact_id_disambiguates(self):
        self.assertEqual(cli.select_target([self.a, self.b], [], {}, device="DEVICE-A", no_input=True), self.a)


class SigningAndParsingTests(unittest.TestCase):
    def test_team_comes_from_ou_not_cn_suffix(self):
        team, org = certificate_subject("subject=\n CN=Apple Development: Example (PERSON0001)\n OU=TEAM000001\n O=Example Org\n")
        self.assertEqual((team, org), ("TEAM000001", "Example Org"))

    def test_conflicting_ous_are_not_guessed(self):
        self.assertIsNone(certificate_subject("OU=TEAM000001\nOU=TEAM000002")[0])

    def test_distribution_identities_are_excluded(self):
        output = ' 1) ' + 'A' * 40 + ' "Apple Development: Example (PERSON0001)"\n 2) ' + 'B' * 40 + ' "Apple Distribution: Example"'
        self.assertEqual(list(development_identities(output)), ['A' * 40])

    def test_explicit_team_wins(self):
        self.assertEqual(cli.select_team("TEAM000003", "TEAM000001", "TEAM000002", []), "TEAM000003")

    def test_project_team_wins_over_saved_value(self):
        self.assertEqual(cli.select_team(None, "TEAM000001", "TEAM000002", []), "TEAM000001")

    def test_multiple_certificate_teams_fail_without_input(self):
        certs = [SigningCertificate("A", "CN", "TEAM000001"), SigningCertificate("B", "CN", "TEAM000002")]
        with self.assertRaises(cli.OneError):
            cli.select_team(None, None, None, certs, True)

    def test_missing_team_has_actionable_setup_error(self):
        with self.assertRaises(cli.OneError) as result:
            cli.select_team(None, None, None, [], True)
        self.assertEqual(result.exception.code, "SIGNING_SETUP")

    def test_invalid_bundle_and_team_rejected(self):
        for invalid in ("org.app;touch /tmp/a", "$(BUNDLE)", "foo", "a..b"):
            with self.subTest(invalid=invalid), self.assertRaises(cli.OneError):
                cli.validate_bundle(invalid)
        with self.assertRaises(cli.OneError):
            cli.validate_team("lowercase1")

    def test_json_with_tool_diagnostics(self):
        self.assertEqual(cli.command_json('Xcode warning\n[{"target":"A"}]\nfinished', list), [{"target": "A"}])

    def test_unrecognized_json_fails(self):
        with self.assertRaises(cli.OneError):
            cli.command_json("Error: missing device", list)

    def test_application_arguments_are_separate_from_cli_options(self):
        args = cli.parse_args(["run", "--no-input", "--", "--team", "literal", "$(literal)"])
        self.assertIsNone(args.team)
        self.assertEqual(args.app_args, ["--team", "literal", "$(literal)"])

    def test_verify_rejects_device_and_application_arguments(self):
        for args in (["verify", "--device"], ["verify", "--", "arg"]):
            with self.subTest(args=args):
                error_output = io.StringIO()
                with contextlib.redirect_stderr(error_output), self.assertRaises(SystemExit) as result:
                    cli.parse_args(args)
                self.assertEqual(result.exception.code, 2)
                self.assertIn("apply only to run/demo", error_output.getvalue())


class FileAndRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ios-one tests ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_workspace_preferred_without_recursive_guessing(self):
        workspace = self.root / "Example.xcworkspace"
        workspace.mkdir()
        (self.root / "Example.xcodeproj").mkdir()
        # macOS temporary directories may use /var, an alias of /private/var.
        self.assertEqual(cli.resolve_container(None, True, self.root), workspace.resolve())

    def test_container_path_is_canonical_through_directory_symlink(self):
        actual = self.root / "actual"
        actual.mkdir()
        workspace = actual / "Example.xcworkspace"
        workspace.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(actual, target_is_directory=True)
        self.assertNotEqual(alias / workspace.name, workspace.resolve())
        for requested in (None, alias / workspace.name):
            with self.subTest(requested=requested):
                self.assertEqual(cli.resolve_container(requested, True, alias), workspace.resolve())

    def test_ambiguous_projects_require_selection(self):
        for name in ("First.xcodeproj", "Second.xcodeproj"):
            (self.root / name).mkdir()
        with self.assertRaises(cli.OneError):
            cli.resolve_container(None, True, self.root)

    def test_config_rejects_malformed_or_unknown_fields(self):
        file = self.root / "settings.json"
        for content in ('not json', '[]', '{"schema":1,"team":42}', '{"schema":1,"shell":"x"}', '{"schema":1,"target_kind":"tv"}'):
            file.write_text(content)
            with self.subTest(content=content), self.assertRaises(cli.OneError):
                cli.read_settings(file)

    def test_settings_atomic_roundtrip_private_mode(self):
        file = self.root / "settings.json"
        cli.write_json(file, {"schema": 1, "scheme": "日本語 with spaces"})
        self.assertEqual(cli.read_settings(file)["scheme"], "日本語 with spaces")
        self.assertEqual(file.stat().st_mode & 0o777, 0o600)

    def test_runner_passes_arguments_without_a_shell(self):
        runner = cli.Runner(self.root, self.root / "state")
        sentinel = self.root / "must-not-exist"
        literal = "$(touch '" + str(sentinel) + "'); `whoami`"
        output = runner.run([sys.executable, "-c", "import sys; print(sys.argv[1])", literal], "literal")
        self.assertEqual(output.strip(), literal)
        self.assertFalse(sentinel.exists())

    def test_failure_exit_does_not_look_successful(self):
        runner = cli.Runner(self.root, self.root / "state")
        with self.assertRaises(cli.OneError):
            runner.run([sys.executable, "-c", "raise SystemExit(7)"], "build")
        self.assertEqual(runner.steps[0]["exit_code"], 7)

    def test_timeout_stops_process(self):
        runner = cli.Runner(self.root, self.root / "state", heartbeat=0.1)
        with self.assertRaises(cli.OneError) as result:
            runner.run([sys.executable, "-c", "import time; time.sleep(10)"], "blocked", timeout=0.25)
        self.assertEqual(result.exception.code, "TIMEOUT")
        self.assertIsNotNone(runner.steps[0]["exit_code"])

    def test_project_lock_prevents_simultaneous_runs(self):
        with cli.project_lock(self.root):
            with self.assertRaises(cli.OneError) as result:
                with cli.project_lock(self.root):
                    pass
        self.assertEqual(result.exception.code, "BUSY")

    def test_shareable_report_omits_private_values(self):
        runner = cli.Runner(self.root, self.root / "state")
        runner.summary.update(xcode_version="15.4", command="run", secret="PRIVATE_SENTINEL")
        runner.steps = [{"step": "signing-subject-PRIVATE_SENTINEL", "command": "PRIVATE_SENTINEL", "log": "PRIVATE_SENTINEL"},
                        {"step": "build", "command": "PRIVATE_SENTINEL", "log": "PRIVATE_SENTINEL", "exit_code": 0, "duration_seconds": 1}]
        runner.finish("passed")
        self.assertNotIn("PRIVATE_SENTINEL", (runner.logs / "shareable-report.json").read_text())
        self.assertIn("PRIVATE_SENTINEL", (runner.logs / "result.json").read_text())

    def test_mismatched_built_app_is_rejected(self):
        app = self.root / "DerivedData/Build/Products/Debug-iphoneos/Example.app"
        app.mkdir(parents=True)
        (app / "Info.plist").write_bytes(plistlib.dumps({"CFBundleIdentifier": "org.wrong.app", "CFBundlePackageType": "APPL"}))
        with self.assertRaises(cli.OneError) as result:
            cli.verify_product({"TARGET_BUILD_DIR": str(app.parent), "FULL_PRODUCT_NAME": app.name}, self.root, "org.expected.app")
        self.assertEqual(result.exception.code, "PRODUCT_ID")

    def test_external_product_path_is_rejected(self):
        with self.assertRaises(cli.OneError) as result:
            cli.verify_product({"TARGET_BUILD_DIR": "/tmp", "FULL_PRODUCT_NAME": "Other.app"}, self.root, "org.app.demo")
        self.assertEqual(result.exception.code, "PRODUCT_PATH")


class ScenarioRunner:
    """A deterministic tool double. These scenarios do not claim Xcode execution."""
    def __init__(self, root, state, fail_step=None, extra_bundle=False, existing_team=""):
        self.root, self.state = root, state
        self.logs = state / "logs"
        self.logs.mkdir(parents=True)
        self.env = {"DEVELOPER_DIR": "/Applications/Xcode.app/Contents/Developer"}
        self.summary, self.calls = {}, []
        self.fail_step, self.extra_bundle, self.existing_team = fail_step, extra_bundle, existing_team
        self.settings = {"PRODUCT_TYPE": "com.apple.product-type.application", "PRODUCT_BUNDLE_IDENTIFIER": "org.example.App",
                         "FULL_PRODUCT_NAME": "Sample App.app", "WRAPPER_EXTENSION": "app", "IPHONEOS_DEPLOYMENT_TARGET": "17.0",
                         "TARGET_BUILD_DIR": str(state / "DerivedData/Build/Products/Debug-iphoneos"),
                         "CODE_SIGN_STYLE": "Automatic", "DEVELOPMENT_TEAM": existing_team}

    def run(self, args, label, **kwargs):
        args = [str(a) for a in args]
        self.calls.append((args, label))
        if label == self.fail_step:
            raise cli.OneError("STEP_FAILED", "simulated failure", label)
        if label == "list-schemes":
            return json.dumps({"project": {"schemes": ["Sample App"]}})
        if label in {"build-settings", "effective-settings"}:
            for arg in args:
                if arg.startswith("PRODUCT_BUNDLE_IDENTIFIER="):
                    self.settings["PRODUCT_BUNDLE_IDENTIFIER"] = arg.split("=", 1)[1]
            rows = [{"target": "Sample App", "buildSettings": dict(self.settings)}]
            if self.extra_bundle:
                rows.append({"target": "Widget", "buildSettings": {"PRODUCT_TYPE": "com.apple.product-type.app-extension", "WRAPPER_EXTENSION": "appex", "PRODUCT_BUNDLE_IDENTIFIER": "org.example.widget", "DEVELOPMENT_TEAM": "TEAM000002"}})
            return json.dumps(rows)
        if label == "build":
            app = Path(self.settings["TARGET_BUILD_DIR"]) / self.settings["FULL_PRODUCT_NAME"]
            app.mkdir(parents=True)
            (app / "Info.plist").write_bytes(plistlib.dumps({"CFBundleIdentifier": self.settings["PRODUCT_BUNDLE_IDENTIFIER"], "CFBundlePackageType": "APPL", "CFBundleExecutable": "Sample App"}))
            (app / "Sample App").write_bytes(b"TEST DOUBLE, NOT A MACH-O EXECUTABLE")
        return ""


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ios-one scenario ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "Unchanged Source/Sample App.xcodeproj"
        self.project.mkdir(parents=True)
        (self.project / "project.pbxproj").write_text("Existing project remains unchanged.")
        self.target = cli.Target("TEST-DEVICE", "Test iPhone", "18.0", "device")

    def run_scenario(self, fail_step=None, extra_bundle=False, existing_team="", extra_args=()):
        runner = ScenarioRunner(self.project.parent, self.root / "cache", fail_step, extra_bundle, existing_team)
        args = cli.parse_args(["run", "--no-input", *extra_args])
        with patch.object(cli, "configure_xcode"), patch.object(cli, "list_devices", return_value=[self.target]), patch.object(cli, "discover_certificates", return_value=[SigningCertificate("A", "Example", "TEAM000001")]):
            try:
                cli.workflow(args, runner, self.project)
            except cli.OneError as error:
                return runner, error
        return runner, None

    def test_full_scenario_uses_build_before_install_before_launch(self):
        runner, error = self.run_scenario(extra_args=["--", "-AppleLanguages", "(ja)"])
        self.assertIsNone(error)
        labels = [label for _, label in runner.calls]
        self.assertLess(labels.index("build"), labels.index("install"))
        self.assertLess(labels.index("install"), labels.index("launch"))
        launch = next(args for args, label in runner.calls if label == "launch")
        self.assertEqual(launch[-3:], ["--", "-AppleLanguages", "(ja)"])
        self.assertEqual((self.project / "project.pbxproj").read_text(), "Existing project remains unchanged.")

    def test_build_failure_never_installs_or_launches(self):
        runner, error = self.run_scenario(fail_step="build")
        self.assertIsNotNone(error)
        self.assertFalse({"install", "launch"} & {label for _, label in runner.calls})

    def test_install_failure_never_launches(self):
        runner, error = self.run_scenario(fail_step="install")
        self.assertIsNotNone(error)
        self.assertNotIn("launch", [label for _, label in runner.calls])

    def test_package_failure_never_builds(self):
        runner, error = self.run_scenario(fail_step="resolve-packages")
        self.assertIsNotNone(error)
        self.assertNotIn("build", [label for _, label in runner.calls])

    def test_bundle_override_rejected_for_extension_scheme(self):
        runner, error = self.run_scenario(extra_bundle=True, extra_args=["--bundle-id", "org.custom.app"])
        self.assertEqual(error.code, "MULTI_BUNDLE")
        self.assertNotIn("build", [label for _, label in runner.calls])

    def test_existing_multi_target_signing_is_preserved(self):
        runner, error = self.run_scenario(extra_bundle=True, existing_team="TEAM000001")
        self.assertIsNone(error)
        build = next(args for args, label in runner.calls if label == "build")
        self.assertFalse(any(arg.startswith(("DEVELOPMENT_TEAM=", "CODE_SIGN_STYLE=", "PRODUCT_BUNDLE_IDENTIFIER=")) for arg in build))

    def test_new_team_not_guessed_for_multi_bundle_scheme(self):
        runner, error = self.run_scenario(extra_bundle=True)
        self.assertEqual(error.code, "MULTI_TEAM")

    def test_saved_demo_id_survives_retry(self):
        runner, error = self.run_scenario(fail_step="build", extra_args=["--bundle-id", "org.custom.stable"])
        self.assertIsNotNone(error)
        settings = cli.read_settings(runner.state / "settings.json")
        self.assertEqual(settings["bundle_id"], "org.custom.stable")

    def test_old_device_detected_before_build(self):
        self.target = cli.Target("OLD", "Older device", "16.0", "device")
        runner, error = self.run_scenario()
        self.assertEqual(error.code, "IOS_VERSION")
        self.assertNotIn("build", [label for _, label in runner.calls])


if __name__ == "__main__":
    unittest.main()
