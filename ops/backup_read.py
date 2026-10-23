#!/usr/bin/env python3
"""Forced SSH command for a read-only, key-restricted backup account."""

import os
import re
import sys
from pathlib import Path

folder = Path("/var/lib/stocklog/backups")
command = os.environ.get("SSH_ORIGINAL_COMMAND", "").strip()
if command == "latest":
    sys.stdout.write((folder / "latest.json").read_text())
elif re.fullmatch(r"get [0-9a-f]{32}", command):
    path = folder / (command.split()[1] + ".tar.gz.age")
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            sys.stdout.buffer.write(chunk)
else:
    sys.stderr.write("Only latest or get <immutable archive ID> is permitted.\n")
    sys.exit(2)
