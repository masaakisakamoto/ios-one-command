import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("publish", Path(__file__).resolve().parents[1] / "scripts/publish.py")
publish = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publish)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        # Mocked successes and expected failures must not look like live results.
        self.error_output = io.StringIO()
        for output in (contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(self.error_output)):
            output.__enter__()
            self.addCleanup(output.__exit__, None, None, None)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "source"
        self.root.mkdir()
        (self.root / "README.md").write_bytes(b"Reviewed public text")
        self.manifest = {"schema": 1, "version": "preview", "files": {"README.md": hashlib.sha256(b"Reviewed public text").hexdigest()}, "executables": []}
        (self.root / "public-files.json").write_text(json.dumps(self.manifest))
        (self.root / ".env").write_text("DO_NOT_UPLOAD=private-test-sentinel")

    def test_preview_runs_no_external_command(self):
        with patch.object(publish, "ROOT", self.root), patch.object(publish, "run") as run, patch.object(publish.subprocess, "run") as raw:
            self.assertEqual(publish.main([]), 0)
        run.assert_not_called()
        raw.assert_not_called()

    def test_changed_source_stops_before_any_remote_command(self):
        (self.root / "README.md").write_text("Edited after review")
        with patch.object(publish, "ROOT", self.root), patch.object(publish, "run") as run:
            self.assertEqual(publish.main(["--public"]), 2)
        self.assertIn("Source differs from the reviewed distribution: README.md", self.error_output.getvalue())
        run.assert_not_called()

    def test_existing_repository_is_never_modified(self):
        calls = []
        def fake_run(args, cwd=None):
            calls.append(args)
            return "example-user" if args[:3] == ["gh", "api", "user"] else ""
        with patch.object(publish, "ROOT", self.root), patch.object(publish, "run", side_effect=fake_run), patch.object(publish.shutil, "which", return_value="/tool"), patch.object(publish.subprocess, "run") as raw:
            raw.return_value.returncode = 0
            self.assertEqual(publish.main(["--public"]), 2)
        self.assertIn("Repository already exists.", self.error_output.getvalue())
        self.assertFalse(any(args[:3] == ["gh", "repo", "create"] for args in calls))

    def test_publication_copies_only_reviewed_files_into_new_git_tree(self):
        calls = []
        def fake_run(args, cwd=None):
            calls.append((args, cwd))
            if args[:3] == ["gh", "api", "user"]:
                return "example-user"
            if args == ["git", "config", "user.name"]:
                return "Example Developer"
            if args == ["git", "config", "user.email"]:
                return "developer@example.invalid"
            return ""
        with patch.object(publish, "ROOT", self.root), patch.object(publish, "run", side_effect=fake_run), patch.object(publish.shutil, "which", return_value="/tool"), patch.object(publish.subprocess, "run") as raw:
            raw.return_value.returncode = 1
            self.assertEqual(publish.main(["--public"]), 0)
        create, stage = next((a, cwd) for a, cwd in calls if a[:3] == ["gh", "repo", "create"])
        self.assertEqual(create[3], "example-user/ios-one-command")
        self.assertIn("--public", create)
        self.assertIn("--push", create)
        self.assertEqual({p.name for p in stage.iterdir()}, {"README.md", "public-files.json"})
        self.assertEqual((self.root / ".env").read_text(), "DO_NOT_UPLOAD=private-test-sentinel")

    def test_invalid_owner_is_rejected(self):
        with patch.object(publish, "ROOT", self.root), patch.object(publish, "run") as run:
            self.assertEqual(publish.main(["--owner", "owner/repo;bad"]), 2)
        self.assertIn("Invalid owner", self.error_output.getvalue())
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
