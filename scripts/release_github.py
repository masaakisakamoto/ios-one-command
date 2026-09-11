#!/usr/bin/env python3
"""Publish a tested preview from GitHub Actions without replacing existing assets."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ios_one import __version__

REPOSITORY = "masaakisakamoto/ios-one-command"


def gh(*args):
    return subprocess.run(["gh", *args], check=True, text=True, capture_output=True).stdout


def releases(repository):
    pages = json.loads(gh("api", "--paginate", "--slurp",
                         "repos/" + repository + "/releases?per_page=100"))
    return [item for page in pages for item in page]


def publish(repository, commit, output):
    if repository != REPOSITORY or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Unexpected repository or commit")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+-preview\.[0-9]+", __version__):
        raise ValueError("This workflow publishes preview versions only")
    tag = "v" + __version__
    existing = next((r for r in releases(repository) if r["tag_name"] == tag), None)
    if existing:
        if existing["draft"]:
            raise ValueError("A draft already exists. Inspect it before retrying; no assets were changed.")
        print("Already published; keeping the existing release: " + existing["html_url"])
        return

    refs = json.loads(gh("api", "repos/" + repository + "/git/matching-refs/tags/" + tag))
    for ref in refs:
        if ref["ref"] == "refs/tags/" + tag:
            if ref["object"]["type"] != "commit" or ref["object"]["sha"] != commit:
                raise ValueError("The release tag already points elsewhere; it was not moved")

    names = ["ios-one-command-" + __version__ + ".zip", "IOS_One_Command_Start.command"]
    assets = [output / name for name in names + ["SHA256SUMS"]]
    expected = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in assets}
    checksum_text = "".join(expected[name] + "  " + name + "\n" for name in names)
    if assets[-1].read_text(encoding="utf-8") != checksum_text:
        raise ValueError("Release checksums do not match the packaged files")
    notes = ROOT / "docs/releases" / (__version__ + ".md")
    if not notes.is_file():
        raise ValueError("Review release notes for this version before publishing")

    gh("release", "create", tag, *(str(path) for path in assets), "--repo", repository,
       "--target", commit, "--title", tag, "--notes-file", str(notes),
       "--draft", "--prerelease", "--latest=false")
    draft = next(r for r in releases(repository) if r["tag_name"] == tag)
    if not draft["draft"] or draft["target_commitish"] != commit:
        raise ValueError("Unexpected release state; inspect the release before retrying")
    uploaded = json.loads(gh("api", "repos/" + repository + "/releases/" + str(draft["id"]) + "/assets"))
    if len(uploaded) != len(expected) or {
        asset["name"]: asset.get("digest") for asset in uploaded
    } != {name: "sha256:" + digest for name, digest in expected.items()}:
        raise ValueError("Uploaded assets failed verification; the release remains a draft")
    gh("release", "edit", tag, "--repo", repository, "--draft=false", "--prerelease", "--latest=false")
    print("Published: " + draft["html_url"])


if __name__ == "__main__":
    if (os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or os.environ.get("GITHUB_EVENT_NAME") not in {"push", "workflow_dispatch"}):
        sys.exit("Run this publisher through the Verify workflow on main.")
    try:
        publish(os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_SHA", ""), ROOT / "dist")
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit("Stopped: " + str(error))
