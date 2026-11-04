"""Release-source validation and conservative deployment recovery boundaries."""

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

OPS = Path(__file__).resolve().parents[1] / "ops"
sys.path.insert(0, str(OPS))
import release  # noqa: E402
import update  # noqa: E402


@pytest.mark.parametrize("value", ["0.1.0", "0.2.1", "1.0.0", "12.34.56"])
def test_version(value):
    assert release.version(value) == tuple(map(int, value.split(".")))


@pytest.mark.parametrize("value", ["v0.1.0", "0.1", "01.2.3", "1.0.0-rc1", "1.0.0\n", None])
def test_bad_version(value):
    with pytest.raises(ValueError):
        release.version(value)


@pytest.mark.parametrize(
    "draft,prerelease,tag",
    [
        (True, False, "v0.1.0"),
        (False, True, "v0.1.0"),
        (False, False, "main"),
        (False, False, "v0.1.0-rc1"),
    ],
)
def test_reject_unstable(draft, prerelease, tag):
    response = io.BytesIO(
        json.dumps(dict(draft=draft, prerelease=prerelease, tag_name=tag)).encode()
    )
    with (
        patch.object(release.urllib.request, "urlopen", return_value=response),
        pytest.raises(ValueError),
    ):
        release.latest()


def test_tag_version_must_match(tmp_path):
    (tmp_path / "stocklog").mkdir()
    (tmp_path / "stocklog/version.json").write_text('{"version":"0.2.0"}')
    with (
        patch.object(release.subprocess, "run"),
        patch.object(release.subprocess, "check_output", return_value="a" * 40),
        pytest.raises(ValueError, match="disagree"),
    ):
        release.fetch({"tag_name": "v0.1.0"}, tmp_path)
    assert not (tmp_path / "release.json").exists()


def test_rollback_requires_identical_migrations_and_dependencies(tmp_path):
    a, b = tmp_path / "old", tmp_path / "new"
    for root in [a, b]:
        (root / "herd/migrations").mkdir(parents=True)
        (root / "herd/migrations/0001.py").write_text("old schema")
        (root / "requirements.lock").write_text("same Django")
    assert update.schema_code(a) == update.schema_code(b)
    (b / "herd/migrations/0002.py").write_text("new schema")
    assert update.schema_code(a) != update.schema_code(b)
    (b / "herd/migrations/0002.py").unlink()
    (b / "requirements.lock").write_text("new Django")
    assert update.schema_code(a) != update.schema_code(b)


def test_health_rejects_wrong_running_commit():
    response = json.dumps({"status": "ok", "version": "0.1.0", "commit": "wrong"})
    with (
        patch.dict(update.os.environ, STOCKLOG_HOSTS="example.test"),
        patch.object(update.subprocess, "check_output", return_value=response),
        pytest.raises(RuntimeError, match="expected release"),
    ):
        update.health({"version": "0.1.0", "commit": "right"})


def test_activation_is_atomic_and_record_follows_release(tmp_path):
    for name in ["old", "new"]:
        (tmp_path / name).mkdir()
        update.write_record(
            tmp_path / name / "release.json", {"version": name, "health": "pending"}
        )
    (tmp_path / "current").symlink_to(tmp_path / "old")
    with patch.object(update, "BASE", tmp_path):
        update.activate(tmp_path / "new")
    assert json.loads((tmp_path / "current/release.json").read_text()) == {
        "version": "new",
        "health": "pending",
    }
    assert (tmp_path / "old/release.json").exists()


def test_fetch_uses_exact_tag_and_records_full_commit(tmp_path):
    (tmp_path / "stocklog").mkdir()
    (tmp_path / "stocklog/version.json").write_text('{"version":"0.1.0"}')
    with (
        patch.object(release.subprocess, "run") as run,
        patch.object(release.subprocess, "check_output", return_value="b" * 40),
    ):
        record = release.fetch({"tag_name": "v0.1.0"}, tmp_path)
    assert any("refs/tags/v0.1.0" in call.args[0] for call in run.call_args_list)
    assert not any("main" in call.args[0] for call in run.call_args_list)
    assert record == json.loads((tmp_path / "release.json").read_text())
    assert record["commit"] == "b" * 40 and record["health"] == "prepared"


def test_real_git_fetch_deploys_published_tag_not_newer_main(tmp_path):
    import subprocess

    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "--quiet", "--initial-branch=main", str(repository)], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "config", "user.name", "Release test"], check=True
    )
    subprocess.run(
        ["git", "-C", str(repository), "config", "user.email", "test@example.test"], check=True
    )
    (repository / "stocklog").mkdir()
    file = repository / "stocklog/version.json"
    file.write_text('{"version":"0.1.0"}')
    subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "commit", "--quiet", "-m", "Stable release"], check=True
    )
    stable_commit = subprocess.check_output(
        ["git", "-C", str(repository), "rev-parse", "HEAD"], text=True
    ).strip()
    subprocess.run(["git", "-C", str(repository), "tag", "v0.1.0"], check=True)
    file.write_text('{"version":"0.2.0"}')
    subprocess.run(
        ["git", "-C", str(repository), "commit", "--quiet", "-am", "Unreleased changes"], check=True
    )
    with patch.object(release, "REPOSITORY", str(repository)):
        record = release.fetch({"tag_name": "v0.1.0"}, tmp_path / "deployed")
    assert record["version"] == "0.1.0" and record["commit"] == stable_commit
    assert (
        json.loads((tmp_path / "deployed/stocklog/version.json").read_text())["version"] == "0.1.0"
    )


@pytest.mark.parametrize("answer,accepted", [("y", True), (" YES ", True), ("n", False), ("", False)])
def test_confirmation_with_nonseekable_terminal(monkeypatch, answer, accepted):
    import builtins
    import os
    import pty
    import select

    master, slave = pty.openpty()
    try:
        terminal = os.ttyname(slave)

        def terminal_open(path, mode):
            assert path == "/dev/tty"
            return builtins.open(terminal, mode)

        # Use real terminal streams: StringIO would conceal the r+ seekability bug.
        monkeypatch.setattr(update, "open", terminal_open, raising=False)
        os.write(master, (answer + "\n").encode())
        assert update.confirm_update() is accepted
        assert select.select([master], [], [], 2)[0], "Confirmation prompt was not written"
        output = os.read(master, 4096).decode()
        assert "Create a backup and deploy this release? [y/N] " in output
    finally:
        os.close(slave)
        os.close(master)
