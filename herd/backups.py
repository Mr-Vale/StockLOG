"""Private encrypted, consistent archives. Filesystem publication follows DB export."""

import contextlib
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction

from .models import Property

SCHEMA_VERSION = 1
APPLICATION_VERSION = "1.0.0"


def migration_fingerprint():
    h = hashlib.sha256()
    for path in sorted((settings.BASE_DIR / "herd/migrations").glob("*.py")):
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()


PATTERN = re.compile(r"^[0-9a-f]{32}$")


def backup_dir():
    path = Path(os.environ.get("STOCKLOG_BACKUPS", settings.STATE_DIR / "backups"))
    path.mkdir(parents=True, exist_ok=True, mode=0o750)
    return path


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@contextlib.contextmanager
def operation_lock():
    lock = backup_dir() / ".operations.lock"
    with lock.open("a") as f:
        if os.geteuid() == 0:
            try:
                import grp
                import pwd

                os.fchown(
                    f.fileno(),
                    pwd.getpwnam("stocklog").pw_uid,
                    grp.getgrnam("stocklog-backup").gr_gid,
                )
                os.fchmod(f.fileno(), 0o640)
            except KeyError:
                pass  # Isolated developer environment may not have production service accounts.
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


@contextlib.contextmanager
def client_defaults(backup=False):
    db = settings.DATABASES["default"]

    def esc(s):
        return str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    fd, name = tempfile.mkstemp(prefix="stocklog-db-", suffix=".cnf")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write("[client]\n")
            for key, value in [
                (
                    "user",
                    os.environ.get("STOCKLOG_BACKUP_DB_USER", db["USER"]) if backup else db["USER"],
                ),
                (
                    "password",
                    os.environ.get("STOCKLOG_BACKUP_DB_PASSWORD", db["PASSWORD"])
                    if backup
                    else db["PASSWORD"],
                ),
                ("host", db["HOST"] or "localhost"),
                ("port", db.get("PORT") or "3306"),
            ]:
                f.write(f'{key}="{esc(value)}"\n')
        yield name
    finally:
        Path(name).unlink(missing_ok=True)


def source_archive(path):
    root = settings.BASE_DIR
    with tarfile.open(path, "w:gz") as tar:
        for name in [
            "manage.py",
            "requirements.in",
            "requirements.lock",
            "requirements-build.lock",
            "requirements-build.in",
            "stocklog",
            "herd",
            "ops",
            "README.md",
            "docs/operations",
        ]:
            p = root / name
            if not p.exists():
                continue
            for item in [p] if p.is_file() else sorted(p.rglob("*")):
                if (
                    not item.is_file()
                    or item.is_symlink()
                    or "__pycache__" in item.parts
                    or item.suffix in [".pyc", ".db", ".sql", ".age"]
                ):
                    continue
                tar.add(item, arcname=str(item.relative_to(root)), recursive=False)


def create_backup():
    recipient = os.environ.get("STOCKLOG_AGE_RECIPIENT", "")
    if not recipient.startswith("age1"):
        raise ValidationError(
            "Configure an age recovery recipient before backups; keep the private recovery key offline."
        )
    folder = backup_dir()
    with (
        operation_lock(),
        tempfile.TemporaryDirectory(prefix=".candidate-", dir=folder) as temp,
    ):
        temp = Path(temp)
        with transaction.atomic():
            list(Property.objects.select_for_update().all())
            with connection.cursor() as c:
                c.execute(
                    "SELECT COALESCE(SUM(data_length+index_length),0) FROM information_schema.tables WHERE table_schema=DATABASE()"
                )
                estimated = int(c.fetchone()[0])
            # Prior archives remain untouched if capacity cannot accommodate a candidate.
            if shutil.disk_usage(folder).free < max(256 * 1024 * 1024, estimated * 3):
                raise ValidationError(
                    "Insufficient free space for a validated backup candidate. Existing backups retained."
                )
            dump = temp / "database.sql"
            with client_defaults(backup=True) as cnf, dump.open("wb") as out:
                subprocess.run(
                    [
                        "mariadb-dump",
                        "--defaults-extra-file=" + cnf,
                        "--single-transaction",
                        "--quick",
                        "--skip-lock-tables",
                        "--no-tablespaces",
                        "--hex-blob",
                        settings.DATABASES["default"]["NAME"],
                    ],
                    stdout=out,
                    stderr=subprocess.PIPE,
                    check=True,
                )
            if dump.stat().st_size < 100:
                raise ValidationError("Database export was unexpectedly empty.")
        source_archive(temp / "release.tar.gz")
        prior_sequence = (
            json.loads((folder / "latest.json").read_text()).get("sequence", 0)
            if (folder / "latest.json").exists()
            else 0
        )
        manifest = {
            "application_version": APPLICATION_VERSION,
            "migration_fingerprint": migration_fingerprint(),
            "sequence": prior_sequence + 1,
            "schema_version": SCHEMA_VERSION,
            "archive_id": uuid.uuid4().hex,
            "created_at": __import__("time").time_ns() // 1000000000,
            "database_sha256": sha(dump),
            "source_sha256": sha(temp / "release.tar.gz"),
            "dependencies_sha256": sha(settings.BASE_DIR / "requirements.lock"),
            "configuration": {
                "database_credentials": "Supply credentials for the new isolated target; old credentials are intentionally excluded.",
                "django_secret_key": "Retain or securely provision a new Django secret; sessions may need renewal.",
                "recovery_key": "External protected age private key required; intentionally excluded.",
            },
        }
        (temp / "manifest.json").write_text(json.dumps(manifest, indent=2))
        clear = temp / "restore.tar.gz"
        with tarfile.open(clear, "w:gz") as tar:
            for name in ["database.sql", "release.tar.gz", "manifest.json"]:
                tar.add(temp / name, arcname=name)
        candidate = temp / "candidate.age"
        subprocess.run(
            ["age", "-r", recipient, "-o", str(candidate), str(clear)],
            check=True,
            stderr=subprocess.PIPE,
        )
        if not candidate.stat().st_size:
            raise ValidationError("Encryption produced no archive.")
        manifest.update(
            {
                "sha256": sha(candidate),
                "size": candidate.stat().st_size,
                "filename": manifest["archive_id"] + ".tar.gz.age",
            }
        )
        dest = folder / manifest["filename"]
        os.chmod(candidate, 0o640)
        # fsync before immutable publication; latest manifest is published last.
        with candidate.open("rb") as f:
            os.fsync(f.fileno())
        os.replace(candidate, dest)
        side = temp / "published.json"
        side.write_text(json.dumps(manifest, indent=2))
        os.chmod(side, 0o640)
        os.replace(side, folder / (manifest["archive_id"] + ".json"))
        latest_temp = folder / ".latest.tmp"
        latest_temp.write_text(json.dumps(manifest, indent=2))
        os.chmod(latest_temp, 0o640)
        os.replace(latest_temp, folder / "latest.json")
        manifests = sorted(
            (json.loads(p.read_text()) for p in folder.glob("*.json") if p.name != "latest.json"),
            key=lambda d: (d.get("sequence", 0), d["created_at"], d["archive_id"]),
            reverse=True,
        )
        for old in manifests[3:]:
            (folder / old["filename"]).unlink(missing_ok=True)
            (folder / (old["archive_id"] + ".json")).unlink(missing_ok=True)
        return manifest


def latest():
    try:
        return json.loads((backup_dir() / "latest.json").read_text())
    except FileNotFoundError:
        raise ValidationError("No completed backup exists.")


def archive_path(identity):
    if not PATTERN.fullmatch(identity):
        raise ValidationError("Invalid immutable archive identity.")
    path = backup_dir() / (identity + ".tar.gz.age")
    if not path.is_file():
        raise ValidationError("This backup has rotated; rediscover latest and retry.")
    return path


def validate_archive(encrypted, key, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    clear = destination / "restore.tar.gz"
    subprocess.run(
        ["age", "-d", "-i", str(key), "-o", str(clear), str(encrypted)],
        check=True,
        stderr=subprocess.PIPE,
    )
    with tarfile.open(clear, "r:gz") as tar:
        members = tar.getmembers()
        if {m.name for m in members} != {
            "database.sql",
            "release.tar.gz",
            "manifest.json",
        } or any(not m.isfile() or m.size > 8 * 1024**3 for m in members):
            raise ValidationError("Unexpected restore archive paths/types/size.")
        for m in members:
            with tar.extractfile(m) as src, (destination / m.name).open("wb") as dst:
                shutil.copyfileobj(src, dst)
    m = json.loads((destination / "manifest.json").read_text())
    if (
        m.get("application_version") != APPLICATION_VERSION
        or m.get("migration_fingerprint") != migration_fingerprint()
    ):
        raise ValidationError(
            "Restore requires the matching application release/migrations. Use the included release source in an isolated target first."
        )
    if m.get("schema_version") != SCHEMA_VERSION:
        raise ValidationError(
            "Incompatible backup schema. Restore with its matching release and documented migration path."
        )
    if (
        sha(destination / "database.sql") != m["database_sha256"]
        or sha(destination / "release.tar.gz") != m["source_sha256"]
    ):
        raise ValidationError("Backup checksum mismatch.")
    with tarfile.open(destination / "release.tar.gz", "r:gz") as source:
        for entry in source.getmembers():
            p = Path(entry.name)
            if p.is_absolute() or ".." in p.parts or not entry.isfile():
                raise ValidationError("Unsafe release archive member.")
    return m


def restore_backup(encrypted, key, confirm_database):
    database = settings.DATABASES["default"]["NAME"]
    if confirm_database != database:
        raise ValidationError("Explicit target database confirmation must match exactly.")
    with operation_lock():
        with connection.cursor() as c:
            c.execute("SHOW TABLES")
            if c.fetchall():
                raise ValidationError(
                    "Restore requires an EMPTY isolated database. Existing installations are never overwritten."
                )
        with tempfile.TemporaryDirectory(prefix="stocklog-restore-") as temp:
            manifest = validate_archive(encrypted, key, temp)
            # The caller runs maintenance mode or targets an isolated fresh installation.
            with (
                client_defaults() as cnf,
                open(Path(temp) / "database.sql", "rb") as source,
            ):
                subprocess.run(
                    [
                        "mariadb",
                        "--defaults-extra-file=" + cnf,
                        "--binary-mode",
                        "--batch",
                        database,
                    ],
                    stdin=source,
                    stderr=subprocess.PIPE,
                    check=True,
                )
            connection.close()
            from django.db.migrations.executor import MigrationExecutor

            executor = MigrationExecutor(connection)
            if executor.migration_plan(executor.loader.graph.leaf_nodes()):
                raise ValidationError(
                    "Restored schema differs from this release. Keep target isolated and use matching source/migrations."
                )
            return manifest
