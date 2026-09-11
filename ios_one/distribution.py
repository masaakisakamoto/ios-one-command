"""Bounded, manifest-checked source distributions; no existing project updates."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import zipfile

MANIFEST = "public-files.json"
PREFIX = "ios-one-command/"
MAX_FILES = 200
MAX_BYTES = 8 * 1024 * 1024


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(name):
    p = PurePosixPath(name)
    if not name or not p.parts or str(p) != name or p.is_absolute() or ".." in p.parts or "\\" in name:
        raise ValueError("Unsafe distribution path")
    if any(part in {".git", ".env", "__pycache__"} for part in p.parts):
        raise ValueError("Non-public distribution path")
    return p


def parse_manifest(data):
    manifest = json.loads(data)
    if not isinstance(manifest, dict) or manifest.get("schema") != 1:
        raise ValueError("Invalid distribution manifest")
    files = manifest.get("files")
    if not isinstance(files, dict) or not 1 <= len(files) <= MAX_FILES or MANIFEST in files:
        raise ValueError("Invalid distribution file list")
    for name, expected in files.items():
        safe_path(name)
        if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
            raise ValueError("Invalid source checksum")
    executables = manifest.get("executables", [])
    if not isinstance(executables, list) or any(p not in files for p in executables):
        raise ValueError("Invalid executable list")
    return manifest


def checked_file(root, name):
    safe_path(name)
    path = root
    for part in PurePosixPath(name).parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("Symlink is not permitted: " + name)
    if not path.is_file():
        raise ValueError("Missing source file: " + name)
    return path


def verify_tree(root):
    if root.is_symlink():
        raise ValueError("Source root cannot be a symlink")
    manifest = parse_manifest(checked_file(root, MANIFEST).read_bytes())
    total = 0
    for name, expected in manifest["files"].items():
        data = checked_file(root, name).read_bytes()
        total += len(data)
        if total > MAX_BYTES or sha256(data) != expected:
            raise ValueError("Source differs from the reviewed distribution: " + name)
    return manifest


def read_archive(data, expected_hash):
    if sha256(data) != expected_hash:
        raise ValueError("Distribution checksum mismatch")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_FILES + 1 or sum(e.file_size for e in entries) > MAX_BYTES:
            raise ValueError("Distribution exceeds limits")
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate archive member")
        files = {}
        for entry in entries:
            if entry.is_dir() or not entry.filename.startswith(PREFIX) or stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError("Unexpected archive member")
            name = entry.filename[len(PREFIX):]
            safe_path(name)
            files[name] = archive.read(entry)
    if MANIFEST not in files:
        raise ValueError("Distribution manifest missing")
    manifest = parse_manifest(files[MANIFEST])
    if set(files) != set(manifest["files"]) | {MANIFEST}:
        raise ValueError("Archive file set differs from manifest")
    for name, expected in manifest["files"].items():
        if sha256(files[name]) != expected:
            raise ValueError("Source checksum mismatch: " + name)
    return manifest, files


def install_archive(data, expected_hash, destination):
    manifest, files = read_archive(data, expected_hash)
    if destination.is_symlink():
        raise ValueError("Install destination cannot be a symlink")
    if destination.exists():
        # Rerunning reuses an identical install. No merge, overwrite or deletion.
        for name, content in files.items():
            if checked_file(destination, name).read_bytes() != content:
                raise ValueError("Existing file changed; preserved without overwrite: " + name)
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".ios-one-stage-", dir=destination.parent))
    try:
        for name, content in files.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            path.chmod(0o755 if name in manifest["executables"] else 0o644)
        # The launcher serializes installation; rename only into an absent path.
        if destination.exists() or destination.is_symlink():
            raise ValueError("Destination appeared during install; retry")
        os.rename(stage, destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return destination
