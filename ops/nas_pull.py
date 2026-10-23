#!/usr/bin/env python3
"""Run via Synology Task Scheduler. Stdlib + OpenSSH; no cPanel/browser login."""

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


def pull(host, user, key, destination, known_hosts):
    folder = Path(destination)
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    ssh = [
        "ssh",
        "-T",
        "-oBatchMode=yes",
        "-oStrictHostKeyChecking=yes",
        "-oUserKnownHostsFile=" + str(known_hosts),
        "-i",
        str(key),
        user + "@" + host,
    ]
    with (folder / ".pull.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        manifest = json.loads(subprocess.check_output(ssh + ["latest"], timeout=60))
        identity = manifest["archive_id"]
        if not re.fullmatch("[0-9a-f]{32}", identity):
            raise ValueError("Invalid archive ID")
        filename = identity + ".tar.gz.age"
        if manifest["filename"] != filename:
            raise ValueError("Unexpected filename")
        target = folder / filename
        if not target.exists():
            fd, temp = tempfile.mkstemp(prefix=".download-", dir=folder)
            try:
                digest = hashlib.sha256()
                size = 0
                with (
                    os.fdopen(fd, "wb") as out,
                    subprocess.Popen(ssh + ["get " + identity], stdout=subprocess.PIPE) as process,
                ):
                    for chunk in iter(lambda: process.stdout.read(1024 * 1024), b""):
                        out.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                    if process.wait() != 0:
                        raise RuntimeError("Transfer failed; existing good backups retained")
                    out.flush()
                    os.fsync(out.fileno())
                if size != manifest["size"] or digest.hexdigest() != manifest["sha256"]:
                    raise ValueError("Incomplete download or checksum mismatch")
                os.replace(temp, target)
            finally:
                Path(temp).unlink(missing_ok=True)
        else:
            digest = hashlib.sha256()
            with target.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != manifest["sha256"]:
                raise ValueError("Existing local backup checksum mismatch; no rotation")
        side = folder / (identity + ".json")
        tmp = folder / ".manifest.tmp"
        tmp.write_text(json.dumps(manifest, indent=2))
        os.replace(tmp, side)
        retained = sorted(
            (json.loads(p.read_text()) for p in folder.glob("*.json")),
            key=lambda m: (m.get("sequence", 0), m["created_at"], m["archive_id"]),
            reverse=True,
        )
        for old in retained[3:]:
            if not re.fullmatch("[0-9a-f]{32}", old["archive_id"]):
                raise ValueError("Invalid retained manifest")
            (folder / (old["archive_id"] + ".tar.gz.age")).unlink(missing_ok=True)
            (folder / (old["archive_id"] + ".json")).unlink(missing_ok=True)
        return identity


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", required=True)
    p.add_argument("--user", default="stocklog-backup")
    p.add_argument("--key", required=True)
    p.add_argument("--known-hosts", required=True)
    p.add_argument("--destination", required=True)
    o = p.parse_args()
    print("Completed backup", pull(o.host, o.user, o.key, o.destination, o.known_hosts))


if __name__ == "__main__":
    main()
