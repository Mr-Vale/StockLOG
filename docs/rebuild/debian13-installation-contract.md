> Implementation was subsequently authorised. This document records preparation decisions; current status, tests and the sole native Debian 13/Caddy deployment are in [the implementation checklist](../IMPLEMENTATION.md) and [operational installation guide](../operations/INSTALL.md). HostGator/cPanel, Python 3.9, MySQL 5.7 and Ubuntu deployment compatibility are superseded requirements.

# Clean Debian 13 installation contract

Owner requirement: the VPS is a clean Debian 13 installation; **all required packages must be installed by the StockLOG installation process**. Do not make the owner assemble undocumented prerequisites. This is a delivery requirement for the future installer, not an implemented or tested installer in this preparation task.

## Supplied baseline

The owner supplied command output showing Debian 13.7 (trixie), Python 3.13.5, 1.9 GiB total RAM / 1.7 GiB available, 1.0 GiB swap unused, and `/dev/vda1` mounted at `/` with 34G total / 842M used / 33G available. Values are rounded as printed by `free -h` and `df -h`. A root SSH shell is shown. This is host-output evidence supplied by the owner, not agent-executed VPS access; it does not show MariaDB, Caddy or Gunicorn installed.

Use this baseline for the deployment plan. Do not require Python 3.9 or replace the distribution Python. Existing swap must be detected and reused, not recreated or doubled by default.

## Installer responsibilities

Provide a versioned installation entry point and documented invocation in this repository when implementation is authorised. Bootstrap from clean Debian 13 using administrative privileges only for system provisioning; install/run the application under a dedicated unprivileged account. Check OS/architecture, free disk/memory, package-manager state and existing services before mutation. Show the planned changes and distinguish first install, upgrade and restore.

The system package manifest must explicitly cover these dependency groups, with package names verified against the actual signed Debian repositories during implementation:

| Group | Required packages/capability |
|---|---|
| Python/venv | `python3`, `python3-venv`, `python3-dev`; bootstrap the application virtualenv's installer tools reproducibly rather than assuming a global pip command |
| MySQL driver build | `build-essential`, `pkg-config`, `default-libmysqlclient-dev` and its resolved runtime libraries for mysqlclient; build only supported verified artifacts |
| Database and export | `mariadb-server`, `mariadb-client`, including compatible `mariadb-dump`; local InnoDB database and narrowly scoped app/migration/backup grants |
| Public HTTP/HTTPS | Caddy from a supported signed package source, with any repository/bootstrap prerequisites included; do not assume it is installed |
| Repository/TLS tooling | `ca-certificates`, `curl`, `gnupg` and required Debian/repository keyrings; use scoped signing keys and keep verification enabled |
| Time, reports and archives | `tzdata`, `fonts-dejavu-core`, `tar`, `gzip`; all additional native libraries needed by the locked report/archive dependencies |
| Process supervision/scheduling/logs | systemd service/timer facilities and log rotation policy; use timers rather than requiring cron if that is the selected implementation |

This list is a planned manifest, not a successful package installation. The final installer must resolve and verify every transitive/native dependency of the actual locked release, including future backup encryption tooling if selected. Do not require Git on the host if installation consumes a verified release archive; if the chosen release path needs Git or another tool, install it explicitly. Do not add Redis, a Node server, Docker, Nginx or cPanel as accidental prerequisites.

Install all Python runtime dependencies into the application virtualenv from a hash-verified dependency lock, including Django, Gunicorn, mysqlclient, ReportLab, openpyxl and XML/import security dependencies and their transitive requirements. Gunicorn is a Python application dependency; Caddy does not execute Python. Build/test-only dependencies must be distinguished from necessary runtime packages. Do not use global pip or disable artifact/TLS/signature checks to make installation succeed.

Create required private paths, permissions, service accounts, application configuration, database configuration/grants, systemd units, Caddy routing, collected static files, backup timer and log limits through supported repeatable setup. Include a supported first-admin setup without a hardcoded password or public registration. Obtain deployment secrets securely and keep them out of command logs/Git. Domain/DNS details are installation inputs, not missing software packages.

Fresh database creation and initial migrations must be explicit; never drop/reinitialise an existing database, replace owner files or rotate credentials on a routine rerun. Preserve existing SSH connectivity/firewall policy; do not silently disable root SSH before a replacement admin login has been verified. Do not run a blanket OS release upgrade, change an existing Caddy site or connect to NAS without authorisation. Record package/source/release versions and setup outcomes without logging secrets.

## Verification required before calling the installer complete

- Exercise the exact documented installation on a fresh Debian 13 test machine, with no preinstalled Caddy/MariaDB/compiler/venv assumed; verify all packages and Python imports are installed by it.
- Verify Gunicorn/Django, Caddy static and reverse-proxy routing, HTTPS when domain/DNS are available, database constraints/transactions, migrations, first-admin setup and service reboot/restart behaviour.
- Run a second installation pass: no data loss, duplicated accounts/timers, changed secrets, duplicate swap or unintended file replacement. Test an interrupted dependency installation and recover cleanly.
- Check disk and peak memory on the 2 GB class host, including build/install time, reports and backup workspaces. Limit build parallelism if needed; use a verified compatible wheel when appropriate rather than assuming source builds are free.
- Validate daily self-contained backup publication/three-version retention and restore to an empty isolated installation, with all required tools installed by the documented process. NAS pull remains a separate authorised operation.

Until these checks run, documentation/package lists are preparation evidence only. No application code or live server is changed by this contract.
