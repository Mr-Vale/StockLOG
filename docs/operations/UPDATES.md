# Releases and updates

## Install and update commands

Run in a root terminal on a blank Debian 13 server:

```sh
apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && installer=$(mktemp /tmp/stocklog-install.XXXXXXXX) && curl --fail --show-error --location https://raw.githubusercontent.com/Mr-Vale/StockLOG/main/ops/bootstrap-install.sh --output "$installer" && bash "$installer"
```

In a root terminal on an existing **versioned** installation, paste:

```sh
updater=$(mktemp /tmp/stocklog-update.XXXXXXXX) && curl --fail --show-error --location https://raw.githubusercontent.com/Mr-Vale/StockLOG/main/ops/update-debian13.sh --output "$updater" && bash "$updater"
```

Alternatively, from the root terminal run `bash /opt/stocklog/current/ops/update-debian13.sh`.
The downloaded wrapper invokes the installed updater; application code still
comes only from the resolved stable tag.

The installed updater (`ops/update-debian13.sh` and `ops/update.py` in
https://github.com/Mr-Vale/StockLOG) checks
`https://api.github.com/repos/Mr-Vale/StockLOG/releases/latest` and fetches the
matching `vMAJOR.MINOR.PATCH` tag from `https://github.com/Mr-Vale/StockLOG.git`.
Fresh installs use precisely the same resolver (`ops/release.py`). The bootstrap
scripts on main are only entry points; the application and its installer come
from the published stable tag. No application update comes from unreleased main.
No release published yet means install/update stops, rather than using main.

The terminal shows installed/available versions, release notes and a confirmation
prompt. Current installations exit without changes. Downgrades are not applied.
A different major version is blocked before preparation or backup. The updater
never invokes the fresh installer, uninstalls anything, or restores a database.

## Version policy

`stocklog/version.json` is the authoritative machine-readable application version.
The interface and terminal display **Version 0.1.0** for the initial release.
`MAJOR.MINOR.PATCH`: increment PATCH for compatible fixes/small UI edits, MINOR
for compatible features, and MAJOR for any change requiring a complete reinstall.
This applies before 1.0: an incompatible change to 0.2.0 must become 1.0.0,
not 0.3.0. Reset lower components when incrementing a higher component.

0.1.0 establishes a baseline for the current property/PIC application; it does
not assert compatibility with old unversioned StockLOG generations. The old
backup schema number 2 describes backup structure, independently of app versions.
Unversioned installations are refused: their missing version/commit cannot be
safely inferred. Assess and migrate them separately, or follow reinstall below.
Do not fabricate a release record to bypass this check.

Each deployed release contains `release.json`: version, full Git commit, tag and
health state. `/opt/stocklog/current/release.json` identifies the active files,
including pending/failed activations. Only `health: healthy` means checks passed.
Settings and `/health/` identify the running code's version and commit.

## Publish a stable release

1. Review compatibility, data-preserving migrations, operational changes and
   rollback implications. Any reinstall requirement means a major increment.
2. Update `stocklog/version.json` and add short release notes to `CHANGELOG.md`.
   Test Debian installation, compatible updates, preservation and failure paths.
3. Merge the reviewed PR, then tag that exact commit, for example:
   `git tag -a v0.1.0 COMMIT_SHA -m 'StockLOG 0.1.0'` and
   `git push origin v0.1.0`.
4. Publish a GitHub Release for that tag using its changelog entry; leave
   **pre-release** unchecked and mark it as the latest stable release. Drafts
   and prereleases are never update candidates. Do not move or reuse release
   tags, delete/recreate releases, or mark an older version as latest.
5. Verify tag, version file and release notes agree. Publication is a separate
   administrator action; creating this PR does not publish a release.

## Preservation and deployment

Updates keep the database, records, accounts, property/PIC settings, app.env,
secrets, recovery key, Caddy domain/HTTPS configuration and backup units untouched.
They reuse the existing Gunicorn service and MariaDB deployment. Compatible
releases must retain that service contract; changes needing a reinstall are major.
No OS packages or service definitions are silently upgraded by the updater.

Preparation checks tools, running services and at least 2 GiB free on release,
state and backup filesystems. The backup mechanism also checks database capacity.
Allow extra space for two dependencies trees, encrypted/decrypted backups and
persistent recovery copies. Installation/update share a nonblocking lock.
The existing backup/restore operation lock protects backup verification and
activation. An operation already holding that lock causes a safe failure.

Dependencies and static files are prepared outside the active release. The
existing backup command makes a consistent encrypted archive; ciphertext,
decryption, inner checksums and schema/source validation must pass. A private
copy of that archive, config/key, Caddy settings and service units is retained in
`/opt/stocklog/recovery/TIMESTAMP/` outside ordinary three-backup rotation. Protect
and copy it off-server; prune manually only after a verified recovery rehearsal.

Downtime covers stopping Gunicorn, migrations, static publication, atomic symlink
activation, restart and local/public HTTPS checks. MariaDB/Caddy stay running.
A compatible update never deletes old releases or recovery copies.

## Major-version reinstall

A different major version always stops the updater, even from 0.x.x. Reinstall
requires a separate, explicit maintenance plan and administrator action:

1. Preserve and verify an encrypted backup, its exact matching release, private
   environment, recovery key, Caddy/domain/HTTPS settings and backup configuration.
   Keep protected off-server copies. Do not delete current records.
2. Follow the target release's reinstall/migration notes. Provision a **separate
   blank Debian 13 target**, using [INSTALL.md](INSTALL.md) and its stable release.
3. Rehearse any documented data conversion in isolation. Restore archives only
   into a new empty schema with their matching source; incompatible backup
   formats require an explicitly supported conversion. Do not import an older
   schema blindly into the new app.
4. Validate accounts, records, property/PIC, secrets, backups and HTTPS, then
   explicitly arrange cutover. Retain the prior server/data until recovery is
   proven. The updater never performs this procedure.

## Recovery

The failed step and previous/prepared release paths are printed. Before activation,
the installed record remains with the old active code. After activation, a failed
release remains pending/failed unless the previous release can safely be restored.
Success is printed only after version/commit and database health checks pass.

If migrations were never attempted, or application migrations **and pinned
runtime dependencies are identical**, automatic code rollback restarts the old
release and checks its health. This conservative rule deliberately refuses
rollback after even a failed migration when schema code differs: MariaDB DDL can
commit independently. No database restoration is attempted.

If rollback cannot be proven safe, Gunicorn stays stopped. Keep the database,
`app.env`, recovery directory and both releases. Inspect:

```sh
journalctl -u stocklog -n 100 --no-pager
cat /opt/stocklog/current/release.json
sudo stocklog-manage showmigrations
```

Have an administrator review the migration state and fix forward with the printed
prepared release. Use its Python/manage.py with `/etc/stocklog/app.env` loaded;
root database access is needed for migrations. Do not mark a release healthy or
switch old code back until schema compatibility is established. If a process was
killed or the host lost power, treat `pending` as an interrupted update, inspect
both releases and database state, and finish the same recovery procedure.

After reviewing and resolving any partial migration, an administrator can finish
forward using the exact prepared path printed by the updater (replace the example
path below). Keep Gunicorn stopped while doing this:

```sh
set -e
prepared=/opt/stocklog/releases/VERSION-COMMIT
set -a; source /etc/stocklog/app.env; set +a
systemctl stop stocklog
STOCKLOG_DB_USER=root STOCKLOG_DB_PASSWORD='' "$prepared/.venv/bin/python" "$prepared/manage.py" migrate --noinput
"$prepared/.venv/bin/python" "$prepared/manage.py" collectstatic --noinput
ln -s "$prepared" /opt/stocklog/recovery-next
mv -Tf /opt/stocklog/recovery-next /opt/stocklog/current
systemctl start stocklog
python3 - <<'PYHEALTH'
import json, sys
from pathlib import Path
root = Path('/opt/stocklog/current').resolve()
sys.path.insert(0, str(root / 'ops'))
from update import health, write_record
record = json.loads((root / 'release.json').read_text())
health(record)  # Requires database, local/public HTTPS and exact version/commit.
write_record(root / 'release.json', dict(record, health='healthy'))
print(f"Recovered Version {record['version']} ({record['commit']})")
PYHEALTH
```

Stop if any command fails; do not skip a failed migration or health check. This
is a manual forward recovery, never a database downgrade.

For recovery from the archive, follow [BACKUP_RESTORE.md](BACKUP_RESTORE.md) with
the matching old source and a **new isolated schema/server**. Compare records
written after the backup and reconcile them before any cutover. Never overwrite
the current database with a pre-update backup. Health failures during rollback
are reported as failures too; check logs and keep the service stopped until fixed.
