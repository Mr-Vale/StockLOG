"""Exercise NAS publication/failure/rotation with a local forced-command transport double.
Actual NAS connectivity is deliberately not attempted.
"""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "nas_pull", Path(__file__).resolve().parents[1] / "ops/nas_pull.py"
)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_nas_temporary_verified_publication_dedup_rotation_and_failure(tmp_path, monkeypatch):
    remote = tmp_path / "remote"
    remote.mkdir()
    bin = tmp_path / "bin"
    bin.mkdir()
    local = tmp_path / "local"
    script = bin / "ssh"
    script.write_text("""#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
base=Path(os.environ['FAKE_BACKUP_REMOTE'])
assert '-oStrictHostKeyChecking=yes' in sys.argv and '-oBatchMode=yes' in sys.argv
command=sys.argv[-1]
if command=='latest':print((base/'latest.json').read_text())
elif command.startswith('get '):sys.stdout.buffer.write((base/(command.split()[1]+'.tar.gz.age')).read_bytes())
else:sys.exit(2)
""")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin) + ":" + __import__("os").environ["PATH"])
    monkeypatch.setenv("FAKE_BACKUP_REMOTE", str(remote))
    for n in range(1, 5):
        identity = f"{n:032x}"
        data = ("Synthetic encrypted-archive transport fixture " + str(n)).encode()
        (remote / (identity + ".tar.gz.age")).write_bytes(data)
        m = {
            "archive_id": identity,
            "filename": identity + ".tar.gz.age",
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
            "created_at": 1600000000 + n,
            "sequence": n,
        }
        (remote / "latest.json").write_text(json.dumps(m))
        module.pull(
            "synthetic.test", "stocklog-backup", "synthetic-key", local, "synthetic-known-hosts"
        )
        module.pull(
            "synthetic.test", "stocklog-backup", "synthetic-key", local, "synthetic-known-hosts"
        )
    assert (
        len(list(local.glob("*.age"))) == 3 and not (local / (f"{1:032x}" + ".tar.gz.age")).exists()
    )
    before = set(local.glob("*.age"))
    m["archive_id"] = f"{5:032x}"
    m["filename"] = m["archive_id"] + ".tar.gz.age"
    (remote / m["filename"]).write_bytes(b"Broken")
    (remote / "latest.json").write_text(json.dumps(m))
    with pytest.raises(ValueError):
        module.pull(
            "synthetic.test", "stocklog-backup", "synthetic-key", local, "synthetic-known-hosts"
        )
    assert set(local.glob("*.age")) == before and not list(local.glob(".download-*"))
