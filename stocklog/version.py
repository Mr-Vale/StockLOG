"""Release version shared by the UI, backup manifests and deployment tools."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = json.loads((ROOT / "stocklog/version.json").read_text())["version"]
if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", VERSION):
    raise ValueError("Invalid StockLOG version")


def identity():
    path = ROOT / "release.json"
    record = json.loads(path.read_text()) if path.exists() else {}
    return {"version": VERSION, "commit": record.get("commit", "development")}
