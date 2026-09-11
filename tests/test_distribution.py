import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile

from ios_one.distribution import MANIFEST, PREFIX, install_archive, read_archive, safe_path, verify_tree


def archive_bytes(changes=None, extra=None):
    data = {"ios-one": b"#!/bin/bash\necho test\n", "README.md": b"Example source\n"}
    manifest = {"schema": 1, "version": "test", "files": {p: hashlib.sha256(b).hexdigest() for p, b in data.items()}, "executables": ["ios-one"]}
    data[MANIFEST] = json.dumps(manifest).encode()
    if changes:
        data.update(changes)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        for name, content in data.items():
            z.writestr(PREFIX + name, content)
        if extra:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                z.writestr(*extra)
    return stream.getvalue()


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.destination = Path(self.temp.name) / "Dev/ios-one-command"

    def test_first_install_and_identical_rerun(self):
        data = archive_bytes()
        digest = hashlib.sha256(data).hexdigest()
        install_archive(data, digest, self.destination)
        before = (self.destination / "README.md").stat().st_mtime_ns
        install_archive(data, digest, self.destination)
        self.assertEqual((self.destination / "README.md").stat().st_mtime_ns, before)
        self.assertEqual((self.destination / "ios-one").stat().st_mode & 0o777, 0o755)
        verify_tree(self.destination)

    def test_existing_edit_stops_without_overwriting_any_file(self):
        data = archive_bytes()
        digest = hashlib.sha256(data).hexdigest()
        install_archive(data, digest, self.destination)
        (self.destination / "README.md").write_text("My changes")
        with self.assertRaises(ValueError):
            install_archive(data, digest, self.destination)
        self.assertEqual((self.destination / "README.md").read_text(), "My changes")

    def test_tampered_outer_checksum_rejected(self):
        with self.assertRaises(ValueError):
            read_archive(archive_bytes(), "0" * 64)

    def test_tampered_inner_file_rejected(self):
        data = archive_bytes(changes={"README.md": b"changed"})
        with self.assertRaises(ValueError):
            read_archive(data, hashlib.sha256(data).hexdigest())

    def test_archive_path_traversal_rejected_before_install(self):
        for path in (PREFIX + "../escape", "/absolute", PREFIX + "a/../../escape", PREFIX + "a\\b"):
            data = archive_bytes(extra=(path, b"unexpected"))
            with self.subTest(path=path), self.assertRaises(ValueError):
                install_archive(data, hashlib.sha256(data).hexdigest(), self.destination)
            self.assertFalse(self.destination.exists())

    def test_duplicate_member_rejected(self):
        data = archive_bytes(extra=(PREFIX + "README.md", b"duplicate"))
        with self.assertRaises(ValueError):
            read_archive(data, hashlib.sha256(data).hexdigest())

    def test_archive_symlink_rejected(self):
        info = zipfile.ZipInfo(PREFIX + "link")
        info.create_system = 3
        info.external_attr = (0o120777 << 16)
        data = archive_bytes(extra=(info, b"/tmp"))
        with self.assertRaises(ValueError):
            read_archive(data, hashlib.sha256(data).hexdigest())

    def test_existing_destination_symlink_rejected(self):
        real = Path(self.temp.name) / "real"
        real.mkdir()
        self.destination.parent.mkdir()
        self.destination.symlink_to(real, target_is_directory=True)
        data = archive_bytes()
        with self.assertRaises(ValueError):
            install_archive(data, hashlib.sha256(data).hexdigest(), self.destination)
        self.assertEqual(list(real.iterdir()), [])

    def test_manifest_cannot_publish_a_symlink(self):
        data = archive_bytes()
        install_archive(data, hashlib.sha256(data).hexdigest(), self.destination)
        (self.destination / "README.md").unlink()
        (self.destination / "README.md").symlink_to("/etc/hosts")
        with self.assertRaises(ValueError):
            verify_tree(self.destination)

    def test_unlisted_file_rejected_in_archive(self):
        data = archive_bytes(extra=(PREFIX + "unlisted.txt", b"unexpected"))
        with self.assertRaises(ValueError):
            read_archive(data, hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    unittest.main()
