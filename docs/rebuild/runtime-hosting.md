# Current hosting target: RackNerd KVM VPS

Updated 23 October 2026. Owner-selected resources: **2 GB RAM, 35 GB SSD, 2 vCPU**, with **Debian 13 or Ubuntu 24.04**. The owner also asked about Caddy; it is the recommended front-end web server in this proposal. No VPS connection, purchase, installation or deployment has occurred.

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

Both OS combinations meet Django 5.2's documented Python/database version requirements. Debian 13 is recommended for a minimal installation with current native package branches; Ubuntu 24.04 remains a reasonable choice if preferred operationally. Do not install a custom Python over the distribution interpreter. Choose one primary OS/engine combination for CI and deployment, with current signed security updates; do not claim both were tested.

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

- Actual VPS OS/image, architecture, usable RAM/storage, swap, administrative provisioning access, SSH reachability and package security updates have not been checked. No credentials are requested now.
- Install/import mysqlclient using the OS client development libraries and Python headers in a virtualenv during authorised setup. The earlier cloud probe lacked those libraries; that is a local setup prerequisite, not an inherent VPS restriction.
- Prove selected MariaDB version, InnoDB, strict SQL mode, utf8mb4/collation, enforced CHECK/FK/unique constraints, READ COMMITTED and concurrent row locks in an isolated test schema. Run actual acceptance against the chosen engine, not SQLite.
- Prove systemd restart behaviour, Caddy-to-Gunicorn requests, static file routing, Django secure-session/CSRF/proxy settings, final-domain HTTPS and restricted network exposure when staging/deployment is authorised.
- Daily archive generation and authenticated discovery, three-version retention, disk-space preflight, restricted NAS transfer and empty-install restore remain unimplemented/unrun. No NAS access is authorised by this plan update.
- Earlier library probes used cloud Python 3.12 and did not validate the VPS, Caddy, Gunicorn or a MariaDB service. The legacy source/archive and three supplied specifications remain unchanged.

Application implementation still awaits the requested design review. Deployment remains outside the authorised preparation scope.
