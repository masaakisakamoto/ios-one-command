#!/usr/bin/env python3
"""Reject personal commit emails without printing their values into CI logs."""
import re
import subprocess
import sys


def public_email(address):
    return (address == "developer@example.invalid"
            or address == "noreply@github.com"
            or bool(re.fullmatch(r"[A-Za-z0-9+_.-]+@users\.noreply\.github\.com", address)))


def check_history():
    output = subprocess.check_output(
        ["git", "log", "--all", "--format=%H%x00%ae%x00%ce"], text=True)
    records = [line.split("\0") for line in output.splitlines()]
    if not records or any(len(row) != 3 or not all(public_email(value) for value in row[1:]) for row in records):
        print("Commit identity check failed: use developer@example.invalid or a GitHub noreply address for both author and committer.", file=sys.stderr)
        return 1
    print("Commit identity check passed; no personal author/committer email detected.")
    return 0


if __name__ == "__main__":
    sys.exit(check_history())
