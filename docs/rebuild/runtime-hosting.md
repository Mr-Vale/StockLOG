# Current hosting target: RackNerd KVM VPS

Updated 23 October 2026. Owner-selected resources: **2 GB RAM, 35 GB SSD, 2 vCPU**. The owner now confirms the VPS has been set up with **Debian 13**; OS selection is complete. Caddy remains the proposed front-end web server. The agent has not connected to or installed/deployed anything on that VPS; installed packages and application services are not verified.

The owner has supplied baseline command output: Debian 13.7, Python 3.13.5, 1.9 GiB total RAM with 1.7 GiB available, 1.0 GiB unused swap, and 33G available on the root filesystem. This resolves the basic OS/Python/resource questions at owner-output evidence level. It is a clean install: **the final StockLOG installer must include all system and application prerequisites**, not assume Caddy/MariaDB/build tools are present. See [installation contract](debian13-installation-contract.md) and [baseline evidence](evidence/vps-baseline.json).

The move supersedes the previous HostGator-specific Python 3.9/Percona 5.7 limitations. Treat MySQL 5.7 compatibility as a constraint of that former plan unless the owner states an independent need for it. Keep [the historical assessment](hostgator-assessment.md) and supplied specification unchanged; later owner instructions determine the current deployment target. No business or acceptance rule changes.

## Recommended stack and OS comparison

| Layer | Debian 13, preferred | Ubuntu 24.04 alternative |
|---|---|---|
| Python | Distribution Python 3.13 in an application virtualenv | Distribution Python 3.12 in an application virtualenv |
| Application | Django 5.2 LTS, latest supported security patch and locked dependencies | Same framework branch |
| Database | MariaDB 11.8, InnoDB | MariaDB 10.11, InnoDB |
| HTTP/TLS/static assets | Caddy with automatic HTTPS | Same |
| Python WSGI server | Gunicorn, private loopback or Unix socket | Same |
| Process supervision/schedule | systemd services; systemd timer or cron for bounded maintenance jobs | Same |
| Exports | ReportLab PDF, openpyxl XLSX | Same |

The owner has selected Debian 13, so Python 3.13 and MariaDB 11.8 are the primary proposed runtime/engine combination for CI and deployment. The Ubuntu column is retained only as prior comparison, not a pending OS decision. Both combinations meet Django 5.2's documented version requirements; neither VPS combination has been tested by the agent. Do not install a custom Python over the distribution interpreter; use signed distribution security updates.

Read-only official distribution package indexes were inspected: Debian trixie main lists Python 3.13 and MariaDB 11.8; Ubuntu noble main lists Python 3.12 and noble universe lists MariaDB 10.11. See [repository metadata evidence](evidence/vps-distro-metadata.json). Exact observed package versions are evidence only, not production pins; security/updates repositories and current apt policy on the actual VPS must determine patched versions. Reading the indexes is not a signature-verified installation or proof of the VPS's installed state. Direct package-information web pages were blocked by the research proxy, but official distribution archive indexes were accessible.

Upstream framework evidence remains: [Django 5.2 Python support](https://github.com/django/django/blob/stable/5.2.x/docs/faq/install.txt), [LTS release notes](https://github.com/django/django/blob/stable/5.2.x/docs/releases/5.2.txt), and [MariaDB/MySQL support](https://github.com/django/django/blob/stable/5.2.x/docs/ref/databases.txt). Django supports Python 3.13 and MariaDB versions above 10.5; no expired-Django or MySQL-5.7 workaround is needed for this proposal.

## Why Caddy fits

Caddy terminates HTTPS, redirects HTTP appropriately, serves public static files and reverse-proxies application requests to Gunicorn. Gunicorn runs Django's WSGI application. Caddy is not a Python runtime or cPanel-style server-management dashboard. Run one public edge web server; Nginx is an alternative, not an additional requirement.

Automatic public HTTPS normally requires a real public domain, correct DNS A/AAAA records, reachable validation ports (normally TCP 80 and 443), suitable firewall rules, and writable persistent Caddy certificate state. Do not publish an AAAA record unless IPv6 works. DNS-challenge or private-network setups require their own verified configuration. An IP-only test is not proof that the final domain's certificate setup works. Preserve Caddy state across restarts and protect any certificate or DNS credentials. No domain is configured and no certificate has been requested in this task.

Authoritative Caddy docs were read through the project's source because direct `caddyserver.com` access returned proxy HTTP 403:

- [Automatic HTTPS](https://github.com/caddyserver/website/blob/master/src/docs/markdown/automatic-https.md)
- [Reverse-proxy quick start](https://github.com/caddyserver/website/blob/master/src/docs/markdown/quick-starts/reverse-proxy.md)
- [Static file server](https://github.com/caddyserver/website/blob/master/src/docs/markdown/caddyfile/directives/file_server.md)

## Initial capacity expectations

Two vCPUs and 2 GB RAM are a reasonable starting allocation for this small, server-rendered 1–10-account application. This is a sizing judgement, not a benchmark or a promise about arbitrary report/import sizes. Use one Gunicorn worker with two threads initially; a MariaDB buffer pool around 256–384 MiB; bounded connection counts, request/import/export sizes and log retention; and a single expensive export/backup at a time where needed. Measure total process memory, peak export/backup memory and latency under the fixture plus representative growth before readiness is claimed.

Avoid a control panel, Redis/Celery, a Node server, a second reverse proxy or Docker unless a demonstrated need justifies their resource/operational cost. They are not initial runtime dependencies. Swap may provide a small emergency cushion if supported; it does not turn a sustained out-of-memory workload into a supported capacity level. The 35 GB SSD must hold OS, releases, database, logs, three completed backups, the next backup's temporary data and free headroom. See [the VPS deployment/resource plan](vps-deployment-plan.md).

## Remaining preflight and evidence boundaries

- Owner-supplied root SSH output establishes Debian 13.7/Python 3.13.5 and the reported RAM/disk/swap baseline. Architecture, package update/security state, installed services and actual application privileges still require installation checks; no agent VPS session has occurred. Do not request the same baseline output again without a new diagnostic reason.
- Install/import mysqlclient using the OS client development libraries and Python headers in a virtualenv during authorised setup. The earlier cloud probe lacked those libraries; that is a local setup prerequisite, not an inherent VPS restriction.
- Prove selected MariaDB version, InnoDB, strict SQL mode, utf8mb4/collation, enforced CHECK/FK/unique constraints, READ COMMITTED and concurrent row locks in an isolated test schema. Run actual acceptance against the chosen engine, not SQLite.
- Prove systemd restart behaviour, Caddy-to-Gunicorn requests, static file routing, Django secure-session/CSRF/proxy settings, final-domain HTTPS and restricted network exposure when staging/deployment is authorised.
- Daily archive generation and authenticated discovery, three-version retention, disk-space preflight, restricted NAS transfer and empty-install restore remain unimplemented/unrun. No NAS access is authorised by this plan update.
- Earlier library probes used cloud Python 3.12 and did not validate the VPS, Caddy, Gunicorn or a MariaDB service. The legacy source/archive and three supplied specifications remain unchanged.

Application implementation still awaits the requested design review. Deployment remains outside the authorised preparation scope.
