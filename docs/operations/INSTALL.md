# StockLOG 2: fresh Debian 13 installation

This release uses a new property/PIC schema. Install into an empty database only. There is no migration of existing test records. The owner will wipe/reinstall the server; development does not touch the VPS.

## One command

On a blank Debian 13 server, log in as root and paste this **single line**. It installs the download prerequisites, downloads the installer to a file, then runs it with terminal input intact.

```sh
apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && installer=$(mktemp /root/stocklog-bootstrap.XXXXXXXX) && curl --fail --show-error --location https://raw.githubusercontent.com/Mr-Vale/StockLOG/feature/property-pic-homepage-installer/ops/bootstrap-debian13.sh --output "$installer" && bash "$installer" feature/property-pic-homepage-installer
```

This command targets the review branch. After merging, use `main` in both places. Bootstrap clones the repository once and checks out a consistent detached revision; it prints that revision. A reviewed commit SHA can be supplied as its argument instead of the branch name. `ops/bootstrap-debian13.sh` and the documented path are tracked in this release.

## Before running

- Blank Debian 13 server and root access (or enter a root shell using `sudo -i`).
- Domain A record points at this server's public IPv4 address. Publish AAAA only with working IPv6.
- TCP 80/443 reachable for Caddy certificate issuance; retain working SSH access.
- Approximately 2 GB RAM and at least 1 GB free installation space, plus room for packages, records and backups.

The installer leaves SSH, firewall and swap policy unchanged.

## Questions and resulting setup

The terminal asks for the public domain, administrator username, and administrator password twice. Password input is hidden and checked by Django (minimum 12 characters; common/numeric/similar passwords rejected). Database credentials and application secrets are generated automatically. There is no default password or public registration.

Installation configures Python 3.13, MariaDB, Caddy, Gunicorn, pinned Python dependencies, an unprivileged app account, empty schema, static files, systemd app service and daily encrypted backup timer. The installed application uses secure cookies, domain/CSRF allowlists and automatic HTTPS. The installer checks local application health, DNS resolution and public HTTPS health before reporting success.

After signing in, add the first property with name, address, owner, optional manager and initial PIC. Add additional PICs from the homepage. Create user accounts through Administration and assign their property access using Manage property access. Administrators can access all properties; standard users see only assigned properties. Save a property/PIC selection to restore it on later logins.

## Paths and checks

- Private environment: `/etc/stocklog/app.env` (root and application group only).
- Backup recovery key: `/etc/stocklog/recovery.key` (root only). Copy to protected off-server storage.
- Releases/current code: `/opt/stocklog/releases/` and `/opt/stocklog/current`.
- Persistent state/static/backups: `/var/lib/stocklog/`.
- App and web server logs: `journalctl -u stocklog -u caddy`.
- Backup logs: `journalctl -u stocklog-backup`.
- App management: `stocklog-manage check --deploy`.

```sh
systemctl status mariadb stocklog caddy stocklog-backup.timer --no-pager
curl --fail https://YOUR_DOMAIN/health/
systemctl start stocklog-backup.service
journalctl -u stocklog-backup -n 50 --no-pager
```

The backup timer runs daily at 16:15 UTC with up to five minutes jitter and missed-run catch-up. Server and NAS each retain three latest successful unique archives. See [backup/restore instructions](BACKUP_RESTORE.md). StockLOG 2 backups have schema version 2 and require matching release/schema fingerprints. Old StockLOG 1 backups must be restored with their matching old release, not this schema.

## Caddy configuration permissions

The installer explicitly makes its Caddy configuration files `root:caddy` with mode `0640`, with a traversable `sites-enabled` directory. It validates the complete configuration as the `caddy` service user before restarting services. This catches unreadable imported files that root validation would miss. Application secrets remain restricted to the StockLOG application group.

## Failures and reruns

The installer reports the failed command line and stops. Fix the underlying error, keeping private configuration and the database. Before a current release has been activated, the same installation command can resume preparation and preserves generated credentials; an existing administrator is never reset. Once `/opt/stocklog/current` exists, reruns refuse to replace the installation. This is a fresh-install entry point, not an automatic updater.

If HTTPS is pending after activation, do not reinstall: check DNS A/AAAA, inbound TCP 80/443 and `journalctl -u caddy`, then retry the HTTPS health check. Check `journalctl -u stocklog` for application failures. Any update to a populated installation requires a separately reviewed, backup-first procedure; never apply this fresh schema over old data.

`--no-start` remains an isolated-image option. It does not verify systemd boot, public DNS or ACME. Full Debian installation/reboot verification must be recorded separately from shell syntax and functional application tests; see [upgrade validation](../testing/PROPERTY_PIC_RESULTS.md).
