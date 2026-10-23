# Historical assessment: HostGator shared hosting

**Superseded deployment target.** The owner subsequently selected a RackNerd KVM VPS (2 GB RAM, 35 GB SSD, 2 vCPU), with Debian 13 or Ubuntu 24.04. Keep this assessment as evidence of earlier constraints; do not apply its Python 3.9/MySQL 5.7 blockers to a fresh VPS. See the [current runtime plan](runtime-hosting.md). The original MySQL 5.7 compatibility target is treated as a HostGator-specific restriction, not a new VPS requirement, unless the owner states it must be retained independently.

Researched locally and from upstream sources on 23 October 2026, then updated with the owner's hosting reply. No hosting/NAS endpoint was contacted and no credentials were supplied. Current provider/plan and versions are owner-reported evidence, not independently executed account checks. A cPanel label alone does not prove Python application support.

## Owner-supplied hosting evidence

| Capability | Supplied details | Status |
|---|---|---|
| Provider/plan | HostGator Hatchling, shared hosting | Reported current plan; not a generic possible provider anymore |
| Python/pip | Python 3.9.25, `/usr/bin/python3`; pip 21.3.1 for Python 3.9 | Reported installed versions; supported newer interpreter or vendor maintenance not established |
| Application Manager | Phusion Passenger | Present according to owner; Python/WSGI application support explicitly **not confirmed** |
| Database target | Percona Server 5.7.44-48; **target MySQL 5.7 compatibility** | Owner's compatibility requirement; do not silently raise it to MySQL 8 |
| DB administration | phpMyAdmin 5.2.3 | UI/tool version, not database server version or proof of app privileges |
| Scheduler/access | Cron available; SSH confirmed working | Owner-confirmed; schedule limits and noninteractive backup access not independently checked |
| SFTP | Not yet confirmed | Remains open; working SSH does not imply SFTP is enabled |
| Export/backup | mysqldump 5.7.44-48 installed; phpMyAdmin Export; cPanel Backup and Backup Wizard | Tools available per owner; consistent self-contained StockLOG export/restore and automation not yet proved |

The exact report is stored as [non-secret evidence](evidence/hosting-owner-report.json). Do not ask the owner to repeat known plan/version/tool details; remaining checks are narrower.

## Decision impact and available paths

The original Django 5.2 proposal is **incompatible with this target**, independently of whether Passenger can run Python: it requires Python >=3.10 and MySQL >=8.0.11 (or MariaDB >=10.5). Updating only Python does not fix the database mismatch; updating only the database does not fix Python. Do not disable Django backend/version checks or fall back to expired Django 4.2.

1. **Preferred supported deployment path:** obtain a supported Python runtime (recommend 3.12 latest patch), a maintained compatible InnoDB database, and confirmed Python WSGI support from the provider or a different plan/host. This would require the owner's agreement to change the stated MySQL 5.7 target; no upgrade, purchase or deployment is authorised or performed here.
2. **Retain MySQL 5.7 compatibility:** revise the backend to a separately verified combination such as Flask plus a MySQL-5.7-capable SQLAlchemy dialect, migration tooling and driver, with explicit account/session/CSRF administration. SQLAlchemy's 2.0 dialect source lists normal MySQL support from 5.6, so a technical SQL compatibility route exists. This is a candidate, not a completed dependency lock or a claim of maintained hosting. Latest observed SQLAlchemy 2.1.6 requires Python >=3.11 and Alembic 1.20.1 >=3.10; do not assume “latest Flask stack” installs on 3.9 simply because Flask 3.1.3 and PyMySQL 1.2.3 advertise >=3.9. Verify any older release line's actual maintenance before selecting it. The Python maintenance/upgrade and Python WSGI prerequisites remain.

MySQL 5.7 does not enforce CHECK constraints. Preserve database-enforced identifier/stock rules through a reviewed and tested alternative such as BEFORE INSERT/UPDATE triggers with SIGNAL, with confirmed trigger grants and backup/restore preservation. Ordinary InnoDB transactions, foreign keys, unique indexes and `SELECT ... FOR UPDATE` are usable concepts, but must still be exercised on the exact Percona target. Do not treat SQLite tests, modern-MySQL-only SQL or ignored CHECK declarations as acceptance evidence. Avoid dependence on window functions, MySQL-8 collations or other MySQL-8-only features in the compatibility path.

CPython 3.9 is end-of-life upstream. Database/provider security backport or extended-maintenance coverage is not established by the Percona version string, cPanel availability or these client tools. Ask the provider for its maintenance/upgrade position; do not assert provider coverage exists or does not exist without evidence. These infrastructure prerequisites do not change animal, finance, allocation, history or acceptance rules.

## Findings

| Component | Evidence | Consequence |
|---|---|---|
| Actual cloud Python | `python --version`: 3.12.14; installed inventory also contains 3.13.5; `python3.9` not found | This cloud machine is not proof of the hosting interpreter. Do not claim 3.9 tested here. |
| Owner-reported hosting Python | Owner now reports 3.9.25 at `/usr/bin/python3`, pip 21.3.1 | Installed version is reported; upgrade/vendor-maintenance options and app virtualenv remain unverified. |
| CPython 3.9 | Upstream PEP 596: end of life 31 October 2025; final security release 3.9.25 | Require a supported interpreter before production delivery. |
| Django 5.2 LTS | Official 5.2 release notes: security support at least three years from April 2025; Python 3.10–3.14; PyPI 5.2.18 metadata `>=3.10` | Recommended maintained branch, with latest security patch locked during implementation. Does not support 3.9. |
| Django 4.2 | Official 5.2 release notes say support ends April 2026 | Reject expired 4.2 as a workaround for Python 3.9. |
| Flask | PyPI 3.1.3 metadata `>=3.9` | A framework compatibility declaration exists for 3.9; that is distinct from a maintained Python runtime. Do not falsely claim no modern framework can import on 3.9. |
| MariaDB/MySQL | Owner reports Percona 5.7.44-48; Django 5.2 requires MariaDB >=10.5 / MySQL >=8.0.11 | Original stack does not fit the requested 5.7 compatibility target. InnoDB/grants/mode still need checking. |
| DB driver | Django recommends mysqlclient; PyPI 2.3.0 requires Python >=3.10 | Cloud source-build probe failed because MySQL/MariaDB client headers/libraries/pkg-config metadata are absent. Host must provide these or a compatible supported wheel. A local failure does not prove the host lacks them. |
| WSGI | Django 5.2.18 minimal WSGI request on cloud Python 3.12 passed HTTP 200 | Framework probe only; no StockLOG implementation, external web server or cPanel verification. |
| PDF/XLSX | ReportLab 5.1.0 and openpyxl 3.1.5 installed/imported; in-memory PDF signature and XLSX round trip passed | Libraries work locally; host installation/fonts/time/memory still require proof. No acceptance reports generated. |
| DB/SSH/cron/export | Cloud has no DB service/client/dump utility; owner confirms host SSH/cron/mysqldump and cPanel export tools | Acknowledge supplied host tools while keeping their StockLOG transaction/backup automation untested. SFTP remains unconfirmed. |

## Sources and retrieval limits

Read the upstream maintainers' documents through GitHub when the environment proxy rejected their documentation domains. These are live branch documents, not a fixed source-release promise; recheck when locking versions. PyPI version values below are observed registry responses, not a claim about installed hosting packages.

- [CPython PEP 596](https://github.com/python/peps/blob/main/peps/pep-0596.rst): explicitly states 3.9 is end-of-life as of 2025-10-31.
- [Django 5.2 install FAQ](https://github.com/django/django/blob/stable/5.2.x/docs/faq/install.txt): compatibility table and advice against end-of-life Python.
- [Django 5.2 release notes](https://github.com/django/django/blob/stable/5.2.x/docs/releases/5.2.txt): LTS designation, support duration, 4.2 end date.
- [Django 5.2 database documentation](https://github.com/django/django/blob/stable/5.2.x/docs/ref/databases.txt): engine minimums, InnoDB, mysqlclient and isolation.
- [mysqlclient installation requirements](https://github.com/PyMySQL/mysqlclient/blob/main/README.md): client development libraries, compiler and pkg-config.
- Registry metadata: [Django 5.2.18](https://pypi.org/pypi/Django/5.2.18/json), [Flask](https://pypi.org/pypi/Flask/json), [mysqlclient](https://pypi.org/pypi/mysqlclient/json), [ReportLab](https://pypi.org/pypi/reportlab/json), [openpyxl](https://pypi.org/pypi/openpyxl/json).
- Follow-up compatibility research: [SQLAlchemy 2.0 MySQL dialect](https://github.com/sqlalchemy/sqlalchemy/blob/rel_2_0/lib/sqlalchemy/dialects/mysql/base.py) lists normal support for MySQL 5.6+; [constraint documentation](https://github.com/sqlalchemy/sqlalchemy/blob/rel_2_0/doc/build/core/constraints.rst) notes lack of active CHECK support before MySQL 8.0.16. Current registry metadata for [SQLAlchemy](https://pypi.org/pypi/SQLAlchemy/json), [Alembic](https://pypi.org/pypi/alembic/json) and [PyMySQL](https://pypi.org/pypi/PyMySQL/json) was inspected to identify interpreter restrictions, not to certify a complete alternative stack. Direct MySQL 5.7 manual request also received proxy tunnel HTTP 403.

Direct requests to `devguide.python.org`, `www.djangoproject.com`, `docs.djangoproject.com`, `docs.cpanel.net` and `www.hostgator.com` were rejected with proxy tunnel HTTP 403. No TLS verification was disabled and no allowlist was changed. The docs failure is a research access restriction, not evidence that the hosting service cannot run StockLOG. Direct cPanel/provider documentation therefore remains unverified; do not infer plan capabilities from brand marketing. If further direct documentation research is needed, those domains need environment access. Raw GitHub/PyPI sources were accessible.

## Non-secret capability evidence needed from the actual plan

Use the owner-supplied evidence above and obtain only remaining provider documentation or read-only account output. Do not send passwords, tokens, connection strings or environment dumps. No deploy/upgrade should occur without the owner's next instruction.

| Capability | Evidence and stage-one gate |
|---|---|
| Python | Available interpreter paths and `python --version` in the app virtualenv, newest supported patch, pip/venv availability. Confirm provider offers 3.12+ and keeps it patched. If 3.9 only, runtime upgrade/change of plan is required. |
| WSGI | Actual “Setup Python App” / Application Manager / Passenger support, entry-point convention, interpreter selection, restart method, URL prefix, static file handling, HTTPS, trusted proxy headers. Later prove a disposable authenticated health endpoint in an approved staging area. |
| Driver | Ability to install/import mysqlclient for that exact interpreter; compiler, Python headers and MariaDB/MySQL client development/runtime libraries or provider-supported wheel. Do not assume host root access or install system packages there. |
| SQL | Percona 5.7.44-48 is reported. Still check InnoDB, strict SQL mode, utf8mb4, FK/unique constraints, transactions, ordinary `SELECT ... FOR UPDATE`, READ COMMITTED and connection TLS if remote. MySQL 5.7 CHECK is unenforced: confirm reviewed trigger/other enforcement and required grants for app/migration/backup accounts. |
| Resources | App memory/CPU, concurrent process limit, request timeout, upload/download and archive size limits, private writable disk quota, cron duration/quota. Test PDF fonts and exports before support is claimed. |
| Cron | Scheduler availability, absolute interpreter path, execution timezone, minimum interval, non-overlap locking and failure log delivery. Scheduling must not depend on a persistent worker. |
| SSH/SFTP/transfer | SSH is owner-confirmed. Still verify SFTP availability or another supported restricted transfer route, noninteractive auth, host-key pinning and private backup directory access. No connection to the owner's NAS is needed for design. |
| Consistent export | mysqldump 5.7.44-48 is reported installed. Still prove `--single-transaction`, necessary narrowly scoped privileges, all intended tables/triggers and portable restore; prohibit schema changes during export. phpMyAdmin/cPanel backup availability alone does not prove the required StockLOG archive contract. |
| Restore | Private maintenance command with explicit target confirmation and maintenance lock; ability to restore into an empty isolated schema, validate and recover failures without touching production. |

The cloud dependency probe environment is `/workspace/stocklog-rebuild-research/venv`, separate from legacy setup. No production dependency manifest or runtime pin was changed in this preparation task. Stage-one implementation will create reproducible dependency locks after resolving the actual target. All database and browser acceptance suites remain unrun.
