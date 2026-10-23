# Runtime and hosting preflight

Verified locally and from upstream sources on 23 October 2026. No hosting/NAS endpoint was contacted; no credentials or hosting configuration were supplied. HostGator and Skyrack are intended possibilities, not verified plans. A cPanel label alone does not prove Python application support.

## Findings

| Component | Evidence | Consequence |
|---|---|---|
| Actual cloud Python | `python --version`: 3.12.14; installed inventory also contains 3.13.5; `python3.9` not found | This cloud machine is not proof of the hosting interpreter. Do not claim 3.9 tested here. |
| Owner-reported hosting Python | Source specification reports 3.9; account not inspected | Actual version/patch and upgrade options remain unknown. |
| CPython 3.9 | Upstream PEP 596: end of life 31 October 2025; final security release 3.9.25 | Require a supported interpreter before production delivery. |
| Django 5.2 LTS | Official 5.2 release notes: security support at least three years from April 2025; Python 3.10–3.14; PyPI 5.2.18 metadata `>=3.10` | Recommended maintained branch, with latest security patch locked during implementation. Does not support 3.9. |
| Django 4.2 | Official 5.2 release notes say support ends April 2026 | Reject expired 4.2 as a workaround for Python 3.9. |
| Flask | PyPI 3.1.3 metadata `>=3.9` | A framework compatibility declaration exists for 3.9; that is distinct from a maintained Python runtime. Do not falsely claim no modern framework can import on 3.9. |
| MariaDB/MySQL | Official Django 5.2 database docs: MariaDB >=10.5 / MySQL >=8.0.11, InnoDB | Actual host engine/version/storage engine unknown. Prefer maintained MariaDB LTS or MySQL 8.4. |
| DB driver | Django recommends mysqlclient; PyPI 2.3.0 requires Python >=3.10 | Cloud source-build probe failed because MySQL/MariaDB client headers/libraries/pkg-config metadata are absent. Host must provide these or a compatible supported wheel. A local failure does not prove the host lacks them. |
| WSGI | Django 5.2.18 minimal WSGI request on cloud Python 3.12 passed HTTP 200 | Framework probe only; no StockLOG implementation, external web server or cPanel verification. |
| PDF/XLSX | ReportLab 5.1.0 and openpyxl 3.1.5 installed/imported; in-memory PDF signature and XLSX round trip passed | Libraries work locally; host installation/fonts/time/memory still require proof. No acceptance reports generated. |
| DB/SSH/cron/export | No MariaDB/MySQL service/client/dump utility found locally; no host evidence | Do not claim production transactions, backups, SFTP or cron tested. |

## Sources and retrieval limits

Read the upstream maintainers' documents through GitHub when the environment proxy rejected their documentation domains. These are live branch documents, not a fixed source-release promise; recheck when locking versions. PyPI version values below are observed registry responses, not a claim about installed hosting packages.

- [CPython PEP 596](https://github.com/python/peps/blob/main/peps/pep-0596.rst): explicitly states 3.9 is end-of-life as of 2025-10-31.
- [Django 5.2 install FAQ](https://github.com/django/django/blob/stable/5.2.x/docs/faq/install.txt): compatibility table and advice against end-of-life Python.
- [Django 5.2 release notes](https://github.com/django/django/blob/stable/5.2.x/docs/releases/5.2.txt): LTS designation, support duration, 4.2 end date.
- [Django 5.2 database documentation](https://github.com/django/django/blob/stable/5.2.x/docs/ref/databases.txt): engine minimums, InnoDB, mysqlclient and isolation.
- [mysqlclient installation requirements](https://github.com/PyMySQL/mysqlclient/blob/main/README.md): client development libraries, compiler and pkg-config.
- Registry metadata: [Django 5.2.18](https://pypi.org/pypi/Django/5.2.18/json), [Flask](https://pypi.org/pypi/Flask/json), [mysqlclient](https://pypi.org/pypi/mysqlclient/json), [ReportLab](https://pypi.org/pypi/reportlab/json), [openpyxl](https://pypi.org/pypi/openpyxl/json).

Direct requests to `devguide.python.org`, `www.djangoproject.com`, `docs.djangoproject.com`, `docs.cpanel.net` and `www.hostgator.com` were rejected with proxy tunnel HTTP 403. No TLS verification was disabled and no allowlist was changed. The docs failure is a research access restriction, not evidence that the hosting service cannot run StockLOG. Direct cPanel/provider documentation therefore remains unverified; do not infer plan capabilities from brand marketing. If further direct documentation research is needed, those domains need environment access. Raw GitHub/PyPI sources were accessible.

## Non-secret capability evidence needed from the actual plan

Obtain provider documentation or read-only account output. Do not send passwords, tokens, connection strings or environment dumps. No deploy/upgrade should occur without the owner's next instruction.

| Capability | Evidence and stage-one gate |
|---|---|
| Python | Available interpreter paths and `python --version` in the app virtualenv, newest supported patch, pip/venv availability. Confirm provider offers 3.12+ and keeps it patched. If 3.9 only, runtime upgrade/change of plan is required. |
| WSGI | Actual “Setup Python App” / Application Manager / Passenger support, entry-point convention, interpreter selection, restart method, URL prefix, static file handling, HTTPS, trusted proxy headers. Later prove a disposable authenticated health endpoint in an approved staging area. |
| Driver | Ability to install/import mysqlclient for that exact interpreter; compiler, Python headers and MariaDB/MySQL client development/runtime libraries or provider-supported wheel. Do not assume host root access or install system packages there. |
| SQL | `SELECT VERSION()` and version comment; InnoDB, strict SQL mode, utf8mb4, enforced CHECK/FK/unique constraints, transactions, ordinary `SELECT ... FOR UPDATE`, READ COMMITTED, connection TLS if remote. Test grants for app schema and separate migration/backup account. |
| Resources | App memory/CPU, concurrent process limit, request timeout, upload/download and archive size limits, private writable disk quota, cron duration/quota. Test PDF fonts and exports before support is claimed. |
| Cron | Scheduler availability, absolute interpreter path, execution timezone, minimum interval, non-overlap locking and failure log delivery. Scheduling must not depend on a persistent worker. |
| SSH/SFTP/transfer | Whether SSH is offered or SFTP-only; restricted noninteractive auth, host-key pinning and private backup directory access. No connection to the owner's NAS is needed for design. |
| Consistent export | Compatible `mariadb-dump`/`mysqldump`, `--single-transaction` and necessary privileges without broad/global grants; prohibit schema changes during export. If tool absent, prove another supported consistent export method before acceptance. |
| Restore | Private maintenance command with explicit target confirmation and maintenance lock; ability to restore into an empty isolated schema, validate and recover failures without touching production. |

The cloud dependency probe environment is `/workspace/stocklog-rebuild-research/venv`, separate from legacy setup. No production dependency manifest or runtime pin was changed in this preparation task. Stage-one implementation will create reproducible dependency locks after resolving the actual target. All database and browser acceptance suites remain unrun.
