#!/usr/bin/env python3
"""Real database/backup/deployment tests; ONLY in the disposable installer image."""

import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

assert Path("/test-source/release.json").exists(), "Disposable installer image required"
sys.path.insert(0, "/src/ops")
import update  # noqa: E402

BASE = Path("/opt/stocklog")
old = (BASE / "current").resolve()
record = json.loads((old / "release.json").read_text())
record["health"] = "healthy"
update.write_record(old / "release.json", record)
config = Path("/etc/stocklog/app.env").read_bytes()
caddy = Path("/etc/caddy/sites-enabled/stocklog.caddy").read_bytes()
timer = Path("/etc/systemd/system/stocklog-backup.timer").read_bytes()
real_run = update.run
pidfile = Path("/tmp/stocklog-update-test.pid")


def services(*args, **kwargs):
    if str(args[0]) != "systemctl":
        return real_run(*args, **kwargs)
    action = str(args[1])
    if action in ("stop", "restart") and pidfile.exists():
        os.kill(int(pidfile.read_text()), signal.SIGTERM)
        for _ in range(100):
            if not pidfile.exists():
                break
            time.sleep(0.1)
    if action in ("start", "restart"):
        root = (BASE / "current").resolve()
        real_run(
            "runuser",
            "-u",
            "stocklog",
            "--",
            root / ".venv/bin/gunicorn",
            "stocklog.wsgi:application",
            "--bind",
            "127.0.0.1:8001",
            "--workers",
            "1",
            "--daemon",
            "--pid",
            pidfile,
            "--chdir",
            root,
        )
        for _ in range(100):
            if pidfile.exists():
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("Test Gunicorn did not publish its PID")
    return subprocess.CompletedProcess(args, 0)


def local_health(expected):
    for _ in range(50):
        try:
            response = subprocess.check_output(
                [
                    "curl",
                    "--fail",
                    "--silent",
                    "-H",
                    "Host: stocklog.example.test",
                    "-H",
                    "X-Forwarded-Proto: https",
                    "http://127.0.0.1:8001/health/",
                ],
                text=True,
            )
            data = json.loads(response)
            assert data["version"] == expected["version"] and data["commit"] == expected["commit"]
            return
        except (subprocess.CalledProcessError, AssertionError):
            time.sleep(0.1)
    raise RuntimeError("Local health failed")


def fixture(release, destination):
    target = release["tag_name"][1:]
    shutil.copytree(
        "/src", destination, ignore=shutil.ignore_patterns(".git", ".venv", "work", "__pycache__")
    )
    (destination / "stocklog/version.json").write_text(json.dumps({"version": target}))
    result = dict(
        version=target, tag="v" + target, commit=(str(version_counter[0]) * 40), health="prepared"
    )
    update.write_record(destination / "release.json", result)
    return result


class Terminal:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def write(self, value):
        pass

    def flush(self):
        pass

    def readline(self):
        return "yes\n"


real_open = open


def terminal(path, *args, **kwargs):
    return Terminal() if str(path) == "/dev/tty" else real_open(path, *args, **kwargs)


def preservation():
    assert Path("/etc/stocklog/app.env").read_bytes() == config
    assert Path("/etc/caddy/sites-enabled/stocklog.caddy").read_bytes() == caddy
    assert Path("/etc/systemd/system/stocklog-backup.timer").read_bytes() == timer
    root = (BASE / "current").resolve()
    update.manage(
        root,
        "shell",
        "-c",
        "from herd.models import Account,Property; assert Account.objects.get(username='installer-test-admin').check_password('Disposable-Installer-Check-2026'); p=Property.objects.get(name='Update preservation property'); assert p.address=='Keep this address'; from herd.models import PIC; pic=PIC.objects.get(number='KEEP0001'); u=Account.objects.get(username='preserved-user'); assert pic.property_id==p.pk and u.pic_id==pic.pk and u.properties.filter(pk=p.pk).exists() and u.check_password('Preserved-User-Password-2026')",
    )


# Seed representative persisted data using the actual property model.
update.manage(
    old,
    "shell",
    "-c",
    "from herd.models import Property; Property.objects.create(name='Update preservation property',address='Keep this address',owner='Existing owner')",
)
update.manage(
    old,
    "shell",
    "-c",
    "from herd.models import Account,Property,PIC; p=Property.objects.get(name='Update preservation property'); pic=PIC.objects.create(property=p,number='KEEP0001'); a=Account.objects.create_user(username='preserved-user',password='Preserved-User-Password-2026',property=p,pic=pic); a.properties.add(p)",
)
services("systemctl", "start", "stocklog")
version_counter = [1]
with (
    patch.object(update, "run", services),
    patch.object(update, "health", local_health),
    patch.object(update, "fetch", fixture),
    patch("builtins.open", terminal),
):

    def attempt(target, fail=None):
        version_counter[0] += 1
        release = dict(tag_name="v" + target, body="Synthetic isolated test release")
        with patch.object(update, "latest", return_value=release):
            if fail:
                try:
                    update.update()
                except Exception as error:
                    assert fail in str(error), (fail, str(error))
                else:
                    raise AssertionError("Expected failure: " + fail)
            else:
                update.update()
        preservation()

    attempt("0.1.0")
    print("PASS already current")
    attempt("1.0.0", "Complete reinstall required")
    print("PASS major blocked")
    with Path("/var/lock/stocklog-install.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        attempt("0.1.1", "Another StockLOG")
    print("PASS simultaneous update prevented")
    with patch.object(update, "fetch", side_effect=RuntimeError("download failure")):
        attempt("0.1.1", "download failure")
    print("PASS failed download preserves installation")
    attempt("0.1.1")
    print("PASS patch update")
    # Pinned recovery timestamp must be unique even during fast tests.
    time.sleep(1.1)
    attempt("0.2.0")
    print("PASS minor update")
    before = (BASE / "current").resolve()
    calls = [0]

    def fail_new_health(expected):
        calls[0] += 1
        if calls[0] == 1:
            raise RuntimeError("injected health failure")
        local_health(expected)

    time.sleep(1.1)
    with patch.object(update, "health", fail_new_health):
        attempt("0.2.1", "injected health failure")
    assert (BASE / "current").resolve() == before
    print("PASS failed health restores compatible code; records/config preserved")
    assert len(list((BASE / "recovery").glob("*/backup.json"))) == 3
    time.sleep(1.1)

    def migrated_fixture(release, destination):
        result = fixture(release, destination)
        (destination / "herd/migrations/0002_update_test.py").write_text(
            "from django.db import migrations\nclass Migration(migrations.Migration):\n    dependencies=[('herd','0001_initial')]\n    operations=[]\n"
        )
        return result

    with (
        patch.object(update, "fetch", migrated_fixture),
        patch.object(update, "health", side_effect=RuntimeError("schema health failure")),
    ):
        attempt("0.3.0", "schema health failure")
    assert (BASE / "current").resolve() != before
    assert not pidfile.exists()
    assert json.loads((BASE / "current/release.json").read_text())["health"] == "failed"
    print("PASS changed migrations prevent automatic rollback; application stopped")
    print("PASS encrypted backups verified and pinned outside rotation")
services("systemctl", "stop", "stocklog")
