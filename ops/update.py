#!/usr/bin/env python3
"""Backup-first native updater. Never restore a database or run the installer."""

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from release import REINSTALL, fetch, latest, version

BASE = Path("/opt/stocklog")
CONFIG = Path("/etc/stocklog")


def run(*args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def write_record(path, record):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(record) + "\n")
    tmp.chmod(0o644)
    os.replace(tmp, path)


def activate(destination):
    link = BASE / "current.next"
    link.unlink(missing_ok=True)
    link.symlink_to(destination)
    os.replace(link, BASE / "current")


def schema_code(root):
    # Dependency changes may alter Django's built-in migrations too.
    digest = hashlib.sha256((root / "requirements.lock").read_bytes())
    for path in sorted((root / "herd/migrations").glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.digest()


def health(record):
    domain = os.environ["STOCKLOG_HOSTS"].split(",")[0]
    for url in ["http://127.0.0.1:8001/health/", f"https://{domain}/health/"]:
        result = subprocess.check_output(
            [
                "curl",
                "--fail",
                "--silent",
                "--show-error",
                "--max-time",
                "15",
                "--retry",
                "5",
                "--retry-delay",
                "2",
                "--retry-connrefused",
                "-H",
                f"Host: {domain}",
                "-H",
                "X-Forwarded-Proto: https",
                url,
            ],
            text=True,
        )
        data = json.loads(result)
        if (
            data.get("status") != "ok"
            or data.get("version") != record["version"]
            or data.get("commit") != record["commit"]
        ):
            raise RuntimeError("Health response does not identify the expected release")


def manage(root, *args, admin=False, **kwargs):
    env = dict(os.environ)
    command = [root / ".venv/bin/python", root / "manage.py", *args]
    if admin:
        env.update(STOCKLOG_DB_USER="root", STOCKLOG_DB_PASSWORD="")
    else:
        command = ["runuser", "-u", "stocklog", "--", *command]
    return run(*command, env=env, **kwargs)


def backup(root, destination):
    # Existing backup code owns its lock. Then hold it through verification and
    # deployment so timers/restores cannot rotate the recovery archive.
    result = subprocess.check_output(
        [
            "runuser",
            "-u",
            "stocklog",
            "--",
            str(root / ".venv/bin/python"),
            str(root / "manage.py"),
            "backup",
        ],
        text=True,
    )
    manifest = json.loads(result)
    folder = Path(os.environ["STOCKLOG_BACKUPS"])
    lock = (folder / ".operations.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    archive = folder / manifest["filename"]
    with archive.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != manifest["sha256"]:
            raise RuntimeError("Backup ciphertext checksum mismatch")
    # Decrypt, verify inner checksums and source/schema using the OLD release.
    code = "from herd.backups import validate_archive; validate_archive(__import__('os').environ['UPDATE_ARCHIVE'], '/etc/stocklog/recovery.key', __import__('os').environ['UPDATE_VERIFY'])"
    with tempfile.TemporaryDirectory(prefix=".verify-", dir=folder) as verify:
        old = dict(os.environ)
        try:
            os.environ.update(UPDATE_ARCHIVE=str(archive), UPDATE_VERIFY=verify)
            manage(root, "shell", "-c", code, admin=True)
        finally:
            os.environ.clear()
            os.environ.update(old)
    # Pin archive outside rotating backup directory; preserve private config too.
    destination.mkdir(mode=0o700)
    shutil.copy2(archive, destination / archive.name)
    shutil.copy2(CONFIG / "app.env", destination / "app.env")
    shutil.copy2(CONFIG / "recovery.key", destination / "recovery.key")
    shutil.copytree("/etc/caddy", destination / "caddy")
    for name in ["stocklog.service", "stocklog-backup.service", "stocklog-backup.timer"]:
        shutil.copy2(Path("/etc/systemd/system") / name, destination / name)
    (destination / "backup.json").write_text(json.dumps(manifest))
    return lock


def update():
    if os.geteuid() != 0:
        raise RuntimeError("Run as root")
    with Path("/var/lock/stocklog-install.lock").open("a") as update_lock:
        try:
            fcntl.flock(update_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another StockLOG installation/update is running")
        old = (BASE / "current").resolve(strict=True)
        record_path = old / "release.json"
        if not record_path.exists():
            raise RuntimeError(
                "Unversioned installation: cannot infer compatibility. Follow " + REINSTALL
            )
        installed = json.loads(record_path.read_text())
        source_version = json.loads((old / "stocklog/version.json").read_text())["version"]
        if installed["version"] != source_version:
            raise RuntimeError(
                "Installed record differs from active source; inspect before updating"
            )
        if installed.get("health") != "healthy":
            raise RuntimeError(
                "Active release has not passed health checks; follow recovery instructions before updating"
            )
        available = latest()
        target = available["tag_name"][1:]
        print(
            f"Installed: Version {installed['version']} ({installed['commit']})\nAvailable: Version {target}",
            flush=True,
        )
        current_version, target_version = version(installed["version"]), version(target)
        if current_version[0] != target_version[0]:
            raise RuntimeError("Complete reinstall required. Nothing changed. See " + REINSTALL)
        if current_version >= target_version:
            print("Already current; no changes made.")
            return
        print(
            available.get("body")
            or "Compatible features/fixes; existing data and configuration will be retained."
        )
        with open("/dev/tty", "r+") as tty:
            tty.write("Create a backup and deploy this release? [y/N] ")
            tty.flush()
            if tty.readline().strip().lower() not in ("y", "yes"):
                print("Cancelled; no changes made.")
                return
        step, stopped, migrated = "prerequisites", False, False
        dest, backup_lock = None, None
        recovery = BASE / "recovery" / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        try:
            for executable in [
                "git",
                "curl",
                "age",
                "mariadb",
                "mariadb-dump",
                "systemctl",
                "runuser",
            ]:
                if not shutil.which(executable):
                    raise RuntimeError("Missing prerequisite: " + executable)
            for path in [
                BASE,
                Path(os.environ["STOCKLOG_STATE"]),
                Path(os.environ["STOCKLOG_BACKUPS"]),
            ]:
                if shutil.disk_usage(path).free < 2 * 1024**3:
                    raise RuntimeError(
                        f"Need at least 2 GiB free at {path}, plus database backup capacity"
                    )
            run("systemctl", "is-active", "--quiet", "stocklog", "mariadb", "caddy")
            step = "download exact published release"
            with tempfile.TemporaryDirectory(prefix=".prepare-", dir=BASE / "releases") as temp:
                prepared = fetch(available, Path(temp) / "source")
                dest = BASE / "releases" / (target + "-" + prepared["commit"])
                if dest.exists():
                    raise RuntimeError(
                        f"Prepared release already exists: {dest}; inspect before retrying"
                    )
                shutil.move(str(Path(temp) / "source"), dest)
            step = "prepare dependencies"
            run("python3", "-m", "venv", dest / ".venv")
            run(
                dest / ".venv/bin/pip",
                "install",
                "--require-hashes",
                "-r",
                dest / "requirements-build.lock",
            )
            run(
                dest / ".venv/bin/pip",
                "install",
                "--no-build-isolation",
                "--require-hashes",
                "-r",
                dest / "requirements.lock",
            )
            run("chmod", "-R", "a+rX", dest)
            manage(dest, "check", "--deploy", "--fail-level", "ERROR")
            step = "prepare static files"
            # Separate static tree; active assets are untouched during preparation.
            env = dict(os.environ, STOCKLOG_STATIC_ROOT=str(dest / "static"))
            run(
                dest / ".venv/bin/python", dest / "manage.py", "collectstatic", "--noinput", env=env
            )
            step = "pre-update backup"
            recovery.parent.mkdir(exist_ok=True, mode=0o700)
            backup_lock = backup(old, recovery)
            step = "stop application"
            stopped = True
            write_record(old / "release.json", dict(installed, health="pending"))
            run("systemctl", "stop", "stocklog")
            step = "database migrations"
            migrated = True  # Even a failed MySQL migration may have committed DDL.
            manage(dest, "migrate", "--noinput", admin=True)
            step = "activate release"
            # Caddy's configured static path remains stable; retain old assets for recovery.
            shutil.copytree(
                dest / "static",
                Path(
                    os.environ.get(
                        "STOCKLOG_STATIC_ROOT", str(Path(os.environ["STOCKLOG_STATE"]) / "static")
                    )
                ),
                dirs_exist_ok=True,
            )
            activate(dest)
            write_record(dest / "release.json", dict(prepared, health="pending"))
            step = "restart application"
            run("systemctl", "start", "stocklog")
            step = "health checks"
            health(prepared)
            write_record(dest / "release.json", dict(prepared, health="healthy"))
            print(f"Update passed health checks: Version {target} ({prepared['commit']})")
        except BaseException:
            print(
                f"Update failed at: {step}. Recovery files: {recovery}. Previous release: {old}",
                file=sys.stderr,
            )
            if stopped:
                safe = not migrated or (dest is not None and schema_code(old) == schema_code(dest))
                if safe:
                    activate(old)
                    write_record(old / "release.json", dict(installed, health="pending"))
                    manage(old, "collectstatic", "--noinput")
                    run("systemctl", "restart", "stocklog")
                    health(installed)
                    write_record(old / "release.json", dict(installed, health="healthy"))
                    print(
                        "Previous application release restored and healthy. Database was not restored.",
                        file=sys.stderr,
                    )
                else:
                    run("systemctl", "stop", "stocklog")
                    active = (BASE / "current").resolve()
                    identity = prepared if active == dest else installed
                    write_record(active / "release.json", dict(identity, health="failed"))
                    print(
                        "Database may have changed. Application stopped; no code/database rollback attempted. "
                        f"Keep {old}, {dest}, and {recovery}. Fix forward using the prepared release; "
                        "See https://github.com/Mr-Vale/StockLOG/blob/main/docs/operations/UPDATES.md#recovery. Never restore over current records.",
                        file=sys.stderr,
                    )
            raise
        finally:
            if backup_lock:
                backup_lock.close()


if __name__ == "__main__":
    import signal

    def interrupted(signum, frame):
        raise RuntimeError(f"Interrupted by signal {signum}")

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        update()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
