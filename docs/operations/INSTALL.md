# Clean Debian 13 installation

Target: RackNerd KVM, Debian 13, Python 3.13, 2 vCPU/2 GB RAM, existing 1 GB swap, roughly 33 GB initially free. One native stack: Caddy, Gunicorn/Django and MariaDB 11.8 with systemd. **No owner VPS/NAS deployment was performed during development.** Read [actual test evidence](../testing/RESULTS.md) before deployment.

## Before transferring a release

Choose the public hostname, property name/PIC and first-admin username. Point its DNS A record to the VPS; publish AAAA only if IPv6 works. Make TCP 80/443 reachable for Caddy/ACME and retain verified SSH administration access. The installer intentionally does not change SSH ports, firewall rules, root login policy or swap. The application does not need publicly reachable database or Gunicorn ports.

Use a reviewed commit from the rebuild branch/draft PR. On a trusted development/workstation checkout:

```sh
git switch rebuild/web-replacement
git pull --ff-only
# Review the exact SHA; do not deploy an unreviewed moving branch automatically.
git rev-parse HEAD
git archive --format=tar --prefix=StockLOG/ HEAD | gzip > StockLOG-release.tar.gz
sha256sum StockLOG-release.tar.gz > StockLOG-release.tar.gz.sha256
scp StockLOG-release.tar.gz StockLOG-release.tar.gz.sha256 root@YOUR_VPS:/root/
```

Git is used on the workstation only; it is not a hidden prerequisite on the clean VPS. Release archives contain no live database or secrets. Verify the SSH host key through the provider/known trusted channel before the first connection. Do not send credentials in chat.

## Install on the clean VPS when ready

Log in using your existing administrative SSH method. Replace `stocklog.YOURDOMAIN` with your real domain, not the documentation placeholder.

```sh
cd /root
sha256sum -c StockLOG-release.tar.gz.sha256
tar -xzf StockLOG-release.tar.gz
bash /root/StockLOG/ops/install-debian13.sh --domain stocklog.YOURDOMAIN
stocklog-manage initial_admin --username YOUR_ADMIN --pic YOUR_PIC --property-name "YOUR PROPERTY"
```

The first-admin command prompts securely for a password; no default password/public registration exists. The command refuses to overwrite an existing installation's accounts/property. Passwords must satisfy Django validation (minimum 12 characters and common-password checks).

The installer installs **all prerequisites**: Python venv/development tooling, native mysqlclient build dependencies, MariaDB server/client/dump, Caddy, certificates/keyrings/TLS tooling, age encryption, fonts, archive utilities, OpenSSH client/server and log rotation. It bootstraps hash-locked build tools then installs hash-verified runtime dependencies without unpinned isolated build requirements. Native packages come from signed Debian repositories; artifact/TLS verification stays enabled. No separately installed pip, Caddy, database, compiler or manual venv is assumed. It does not use Docker or install Node/Redis/Celery/cPanel/Nginx.

System changes: unprivileged `stocklog` service account, restricted `stocklog-backup` transfer account (no key configured until explicitly enabled), private random configuration under `/etc/stocklog`, MariaDB schema/users with separate runtime/backup grants, root-owned releases under `/opt/stocklog/releases`, `/opt/stocklog/current`, persistent `/var/lib/stocklog`, systemd units/timer, a managed Caddy site, log limits and recovery key. Existing config/secrets are retained on rerun. Unrelated Caddy configuration is refused rather than silently overwritten; the packaged default is preserved as `/etc/caddy/Caddyfile.stocklog-original`.

Copy `/etc/stocklog/recovery.key` to **protected off-server recovery storage** before relying on backups. It is the private key needed to decrypt backups; do not commit it, put it in a public share, or rely on its VPS copy alone. The NAS needs only the restricted SSH transfer key, not this decryption key. See [backup/key custody and restore](BACKUP_RESTORE.md).

## Check installation before real records

```sh
systemctl status mariadb stocklog caddy stocklog-backup.timer --no-pager
systemctl list-timers stocklog-backup.timer --all
journalctl -u stocklog -u caddy -n 100 --no-pager
curl --fail https://stocklog.YOURDOMAIN/health/
stocklog-manage check --deploy
systemctl start stocklog-backup.service
journalctl -u stocklog-backup -n 50 --no-pager
```

Check public HTTPS sign-in, CSRF-protected preview/confirmation, a synthetic disposable record workflow, static CSS/JS, and service restart. The installer uses production secure cookies, HTTPS redirects, host/CSRF-origin allowlists and a content security policy. HSTS is set on the application hostname; Django's optional subdomain/preload policy warnings are not silently converted to global domain policy. Decide whether broader HSTS coverage is appropriate before changing it.

Backups run at **16:15 UTC daily**, with up to five minutes jitter and missed-run catch-up. This corresponds to 02:15 AEST / 03:15 AEDT the next day in Sydney/Melbourne. Business event timezone remains a property setting, independent of scheduling. Verify the first completed encrypted backup and an isolated restore before entering real operational data. No NAS connection is made by installation.

## Capacity and persistent state

Start with one Gunicorn worker/two threads, soft/hard worker-service memory limits 512/768 MiB, MariaDB buffer pool 384 MiB, maximum 20 DB connections, bounded import sizes and capped logs. The existing swap is left unchanged. `/var/lib/stocklog/backups` keeps the three latest successful unique archives, and publication also needs space for the next candidate and dump. Failures do not delete prior good versions. Watch disk/DB growth and peak report/backup memory; 35 GB is finite and indefinite retention does not permit automatic business-data purge.

Application/backup output goes to journald (128 MiB disk / 32 MiB runtime limits); the optional application file-log directory has four compressed weekly rotations. Use `journalctl` and systemd exit status to monitor failed timer runs. No external notification delivery is configured automatically.

## Updates and failures

The install entry point is repeatable: transfer a new reviewed release and invoke it with the same domain. It refuses unexpected domains/configuration, preserves secrets/accounts/data, installs a versioned release, serialises against backup operations, stops the web service before migrations, validates configuration and switches `/opt/stocklog/current` only after preparation. Back up first and schedule an update window; migrations and MariaDB package/restart operations can cause downtime. It is not a zero-downtime deployment system.

A failed update can leave the web service stopped for diagnosis. Review the logs and database migration state; do not blindly reset a populated database or run old code against a changed schema. Retained release directories support code rollback only when schema compatibility is verified. For data recovery use a validated isolated restore and explicit activation, retaining the old database and private pre-restore configuration.

`--no-start` is an **isolated image/test option**, not a production install recommendation. It starts MariaDB through the available service helper but skips systemd application/Caddy startup. Tests using this option cannot claim real systemd PID-1 boot or public ACME issuance is verified. Production installation uses the normal command above.
