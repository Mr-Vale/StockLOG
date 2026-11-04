#!/usr/bin/env python3
"""Resolve published stable releases and fetch an exact, validated version tag."""

import json
import re
import subprocess
import urllib.request
from pathlib import Path

REPOSITORY = "https://github.com/Mr-Vale/StockLOG.git"
API = "https://api.github.com/repos/Mr-Vale/StockLOG"
REINSTALL = "https://github.com/Mr-Vale/StockLOG/blob/main/docs/operations/UPDATES.md#major-version-reinstall"


def version(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value
    ):
        raise ValueError("Expected MAJOR.MINOR.PATCH")
    return tuple(map(int, value.split(".")))


def latest():
    request = urllib.request.Request(
        API + "/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "StockLOG-updater"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    tag = data["tag_name"]
    if data["draft"] or data["prerelease"] or not tag.startswith("v"):
        raise ValueError("No published stable version tag")
    version(tag[1:])
    return data


def fetch(release, destination):
    tag = release["tag_name"]
    version(tag[1:])
    destination = Path(destination)
    subprocess.run(["git", "init", "--quiet", str(destination)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(destination),
            "fetch",
            "--quiet",
            "--depth=1",
            REPOSITORY,
            "refs/tags/" + tag,
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(destination), "checkout", "--quiet", "--detach", "FETCH_HEAD"], check=True
    )
    commit = subprocess.check_output(
        ["git", "-C", str(destination), "rev-parse", "HEAD"], text=True
    ).strip()
    actual = json.loads((destination / "stocklog/version.json").read_text())["version"]
    if actual != tag[1:]:
        raise ValueError("Published tag and application version disagree")
    record = {"version": actual, "commit": commit, "tag": tag, "health": "prepared"}
    (destination / "release.json").write_text(json.dumps(record) + "\n")
    return record


if __name__ == "__main__":
    import sys

    result = fetch(latest(), sys.argv[1])
    print(f"Version {result['version']} ({result['commit']})")
