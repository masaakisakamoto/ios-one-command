#!/usr/bin/env python3
"""Publish exactly the reviewed source set as a new public GitHub repository."""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ios_one.distribution import MANIFEST, verify_tree


def run(arguments, cwd=ROOT):
    result = subprocess.run(arguments, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env={**os.environ, "GH_HOST": "github.com"})
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Command failed: " + arguments[0])
    return result.stdout.strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Preview a new public repository; add --public to create and push it.")
    parser.add_argument("--owner", help="defaults to the signed-in GitHub user")
    parser.add_argument("--name", default="ios-one-command")
    parser.add_argument("--public", action="store_true", help="create the public repository and push the reviewed source")
    args = parser.parse_args(argv)
    stage = None
    try:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", args.name):
            raise ValueError("Invalid repository name")
        if args.owner and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", args.owner):
            raise ValueError("Invalid owner")
        manifest = verify_tree(ROOT)
        print("Public source files: %d | version: %s" % (len(manifest["files"]) + 1, manifest["version"]))
        print("Repository: %s/%s" % (args.owner or "<signed-in GitHub user>", args.name))
        print("Visibility: PUBLIC | release status: preview; validated scope is recorded in docs/validation.md.")
        if not args.public:
            print("Preview only. To publish this exact source set: bash Publish_GitHub.command --public")
            return 0
        if not shutil.which("gh"):
            raise RuntimeError("GitHub CLI is required. Install gh and run: gh auth login")
        if not shutil.which("git"):
            raise RuntimeError("Git is required.")
        run(["gh", "auth", "status", "--hostname", "github.com"])
        owner = args.owner or run(["gh", "api", "user", "--jq", ".login"])
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", owner):
            raise ValueError("Invalid authenticated owner")
        repository = owner + "/" + args.name
        existing = subprocess.run(["gh", "repo", "view", repository, "--json", "nameWithOwner"], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env={**os.environ, "GH_HOST": "github.com"})
        if existing.returncode == 0:
            raise RuntimeError("Repository already exists. Nothing was changed: " + repository)
        print("› pre-publication-tests …", flush=True)
        run([sys.executable, "-m", "unittest", "discover", "-s", "tests"])
        print("Pre-publication tests passed.", flush=True)
        # Check author configuration before any remote mutation; do not invent identity.
        try:
            author_name = run(["git", "config", "user.name"])
            author_email = run(["git", "config", "user.email"])
        except RuntimeError as error:
            raise RuntimeError("Set your intended Git user.name and user.email before publication.") from error
        if not author_name or not author_email:
            raise RuntimeError("Set your intended Git user.name and user.email before publication.")
        stage = Path(tempfile.mkdtemp(prefix=args.name + "-public-", dir=ROOT.parent))
        for name in [*manifest["files"], MANIFEST]:
            destination = stage / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)
            destination.chmod(0o755 if name in manifest["executables"] else 0o644)
        verify_tree(stage)
        run(["git", "init", "--initial-branch=main"], stage)
        run(["git", "config", "user.name", author_name], stage)
        run(["git", "config", "user.email", author_email], stage)
        run(["git", "add", "--", "."], stage)
        run(["git", "commit", "-m", "Initial ios-one-command preview"], stage)
        run(["gh", "repo", "create", repository, "--public", "--source", str(stage), "--remote", "origin", "--push",
             "--description", "Build, install and launch an iOS app from one command. Local Xcode tools, guided setup, Japanese and English."], stage)
        print("Published: https://github.com/" + repository)
        print("Git working copy: " + str(stage))
        return 0
    except (ValueError, OSError, RuntimeError) as error:
        print("Stopped: " + str(error), file=sys.stderr)
        if stage is not None:
            print("Prepared Git source retained for recovery: " + str(stage), file=sys.stderr)
            print("If repository creation succeeded but the push failed, inspect gh repo view and git remote -v in that folder, then retry git push -u origin main. Do not recreate or force-push.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
