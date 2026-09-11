import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from scripts import release_github as release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.output = Path(temp.name)
        self.tag = "v" + release.__version__
        self.commit = "a" * 40
        names = ["ios-one-command-" + release.__version__ + ".zip", "IOS_One_Command_Start.command"]
        for name in names:
            (self.output / name).write_bytes(b"test release asset")
        checksums = "".join(hashlib.sha256((self.output / name).read_bytes()).hexdigest()
                            + "  " + name + "\n" for name in names)
        (self.output / "SHA256SUMS").write_text(checksums)
        self.uploaded = [{"name": name, "digest": "sha256:" + hashlib.sha256((self.output / name).read_bytes()).hexdigest()}
                         for name in names + ["SHA256SUMS"]]
        self.draft = {"id": 7, "tag_name": self.tag, "draft": True,
                      "target_commitish": self.commit, "html_url": "https://example.invalid/release"}

    def publish(self):
        with redirect_stdout(io.StringIO()):
            release.publish(release.REPOSITORY, self.commit, self.output)

    def test_published_release_is_not_replaced(self):
        existing = dict(self.draft, draft=False)
        with mock.patch.object(release, "releases", return_value=[existing]), mock.patch.object(release, "gh") as gh:
            self.publish()
        gh.assert_not_called()

    def test_partial_draft_is_not_overwritten(self):
        with mock.patch.object(release, "releases", return_value=[self.draft]), mock.patch.object(release, "gh") as gh:
            with self.assertRaisesRegex(ValueError, "draft already exists"):
                self.publish()
        gh.assert_not_called()

    def test_tag_for_another_commit_stops_before_upload(self):
        refs = [{"ref": "refs/tags/" + self.tag, "object": {"type": "commit", "sha": "b" * 40}}]
        with mock.patch.object(release, "releases", return_value=[]), mock.patch.object(release, "gh", return_value=json.dumps(refs)) as gh:
            with self.assertRaisesRegex(ValueError, "tag already points elsewhere"):
                self.publish()
        self.assertTrue(all(call.args[0] == "api" for call in gh.call_args_list))

    def test_modified_local_asset_stops_before_upload(self):
        (self.output / "IOS_One_Command_Start.command").write_bytes(b"modified after packaging")
        with mock.patch.object(release, "releases", return_value=[]), mock.patch.object(release, "gh", return_value="[]") as gh:
            with self.assertRaisesRegex(ValueError, "checksums do not match"):
                self.publish()
        self.assertTrue(all(call.args[0] == "api" for call in gh.call_args_list))

    def test_uploaded_digest_mismatch_keeps_release_draft(self):
        self.uploaded[0]["digest"] = "sha256:" + "0" * 64
        with mock.patch.object(release, "releases", side_effect=[[], [self.draft]]), mock.patch.object(
            release, "gh", side_effect=["[]", "", json.dumps(self.uploaded)]
        ) as gh:
            with self.assertRaisesRegex(ValueError, "remains a draft"):
                self.publish()
        self.assertFalse(any(call.args[:2] == ("release", "edit") for call in gh.call_args_list))

    def test_publish_only_after_uploaded_assets_match(self):
        with mock.patch.object(release, "releases", side_effect=[[], [self.draft]]), mock.patch.object(
            release, "gh", side_effect=["[]", "", json.dumps(self.uploaded), ""]
        ) as gh:
            self.publish()
        creation = gh.call_args_list[1].args
        self.assertIn("--draft", creation)
        self.assertEqual(creation[creation.index("--target") + 1], self.commit)
        self.assertEqual(gh.call_args_list[-1].args[:3], ("release", "edit", self.tag))
        self.assertIn("--draft=false", gh.call_args_list[-1].args)


if __name__ == "__main__":
    unittest.main()
