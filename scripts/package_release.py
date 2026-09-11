#!/usr/bin/env python3
"""Build a public source ZIP and a self-contained Mac launcher."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shlex
import sys
import textwrap
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ios_one import __version__
from ios_one.distribution import MANIFEST, PREFIX, safe_path, verify_tree

ROOT_FILES = {"README.md", "README.ja.md", "LICENSE", "CHANGELOG.md", "CONTRIBUTING.md", ".gitignore",
              "ios-one", "Try_Demo.command", "Verify_On_Mac.command", "Publish_GitHub.command"}
DIRECTORIES = {"ios_one", "scripts", "tests", "docs", "examples", ".github"}
EXTENSIONS = {".py", ".swift", ".md", ".yml", ".yaml", ".json", ".pbxproj", ".xcscheme"}


def source_files():
    result = []
    for path in sorted(ROOT.rglob("*")):
        rel = path.relative_to(ROOT)
        name = rel.as_posix()
        selected = name in ROOT_FILES or (rel.parts[0] in DIRECTORIES and path.suffix in EXTENSIONS and "__pycache__" not in rel.parts)
        if not selected:
            continue
        if path.is_symlink():
            raise ValueError("Source symlink: " + name)
        if path.is_file():
            safe_path(name)
            result.append(name)
    missing = ROOT_FILES - set(result)
    if missing:
        raise ValueError("Missing public files: " + ", ".join(sorted(missing)))
    return result


def package(output):
    names = source_files()
    executables = [name for name in names if name == "ios-one" or name.endswith(".command")]
    manifest = {"schema": 1, "version": __version__, "files": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}, "executables": executables}
    (ROOT / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    verify_tree(ROOT)
    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / ("ios-one-command-" + __version__ + ".zip")
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in names + [MANIFEST]:
            info = zipfile.ZipInfo(PREFIX + name, date_time=(2026, 9, 11, 0, 0, 0))
            info.create_system = 3
            info.external_attr = ((0o100755 if name in executables else 0o100644) << 16)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (ROOT / name).read_bytes())
    payload = archive_path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    # The bootstrap module is included literally; no installed package is needed.
    bootstrap = (ROOT / "ios_one/distribution.py").read_text(encoding="utf-8")
    bootstrap += '''
import base64
import fcntl
import sys
if sys.version_info < (3, 9):
    sys.exit("Python 3.9+ is required. / Python 3.9以降が必要です。")
launcher = Path(sys.argv[1]).resolve()
payload = base64.b64decode(launcher.read_bytes().split(b"\\n__IOS_ONE_PAYLOAD__\\n", 1)[1])
destination = Path.home() / "Dev/ios-one-command"
destination.parent.mkdir(parents=True, exist_ok=True)
try:
    with (destination.parent / ".ios-one-install.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        install_archive(payload, EXPECTED_HASH, destination)
    print("準備完了 / Ready: " + str(destination), flush=True)
    if sys.argv[2:] == ["--install-only"]:
        sys.exit(0)
    os.execv("/bin/bash", ["/bin/bash", str(destination / "ios-one"), "demo", "--lang", "ja", *sys.argv[2:]])
except (ValueError, OSError, zipfile.BadZipFile) as error:
    sys.exit("停止 / Stopped: " + str(error))
'''
    bootstrap = "EXPECTED_HASH = " + repr(digest) + "\n" + bootstrap
    header = '''#!/bin/bash
set -euo pipefail
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo 'XcodeのあるMacで実行してください。 / Run on a Mac with Xcode.' >&2
  exit 2
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo 'Python 3.9以降が必要です。 / Python 3.9+ is required.' >&2
  exit 2
fi
exec python3 -c ''' + shlex.quote(bootstrap) + ' "$0" "$@"\n'
    launcher = output / "IOS_One_Command_Start.command"
    launcher.write_text(header + "__IOS_ONE_PAYLOAD__\n" + "\n".join(textwrap.wrap(base64.b64encode(payload).decode(), 100)) + "\n", encoding="utf-8")
    launcher.chmod(0o755)
    checksums = output / "SHA256SUMS"
    checksums.write_text("".join(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name + "\n"
                                 for path in (archive_path, launcher)), encoding="utf-8")
    print(json.dumps({"zip": str(archive_path.resolve()), "zip_sha256": digest,
                      "launcher": str(launcher.resolve()), "checksums": str(checksums.resolve()),
                      "public_files": len(names) + 1}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    package(parser.parse_args().output.resolve())
