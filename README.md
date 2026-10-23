# StockLOG

A responsive cattle-management web application for a single property and small team. It records permanent animal identities and tag lineage, purchases/births/repurchases, historical mobs, sales/deaths, feed and chemical stock, treatments/procedures, lifetime AUD finances and LPA record exports.

Production target: **clean Debian 13 on the owner's RackNerd KVM VPS, 2 vCPU / 2 GB RAM, existing 1 GB swap, approximately 33 GB initially free**. One native deployment: **Caddy → Gunicorn → Django 5.2 LTS → MariaDB 11.8 InnoDB**, supervised by systemd. The installer includes system/native/Python prerequisites. No Docker, Node server, cPanel, HostGator, Python 3.9 or MySQL 5.7 production compatibility is required. Those earlier constraints are explicitly superseded by the owner's implementation approval.

## Installation and operation

- [Exact clean-Debian installation and upgrade steps](docs/operations/INSTALL.md)
- [Encrypted backups, NAS pull, recovery keys and fresh-install restore](docs/operations/BACKUP_RESTORE.md)
- [Business rules and implementation traceability](docs/IMPLEMENTATION.md)
- [Actual validation, report files and remaining verification](docs/testing/RESULTS.md)
- [Original replacement specification](docs/specifications/StockLOG_rebuild_agent_prompt.md), [independent acceptance scenario](docs/testing/StockLOG_acceptance_scenario.md), [LPA field mapping](docs/rebuild/lpa-field-mapping.md)

Initial production data is empty. There is no legacy migration, public signup, default password, photo/document attachment store, initial weight/map/paddock-management interface, or predictive animal valuation. Database/archive compatibility is explicit, not an arbitrary future-version restore promise.

## Core behaviour

- Either a 16-character NLIS visual identifier or 15-ASCII-digit RFID registers an animal; both are strings. Permanent reservations survive exits, deaths, tag changes and eligible retention redaction. IDs never silently merge animals.
- All mutations use property-scoped transactions and serialised inventory/membership checks. Decimal quantities, prices and allocations retain sub-cent precision. Costs use actual event-time members and frozen cost basis.
- Feed may cross from positive into negative once; subsequent nonpositive-stock feeding is blocked. Chemicals never go negative and doses are never adjusted/recommended automatically. Stocktakes/refills do not reprice past animals.
- Standard users can reverse their own eligible actions before 24 hours; administrators handle older/other-user actions, every sale/death reversal, historical mob corrections, identifier conflict reviews and deliberate eligible purge. Conflicting later events are refused, not partially reversed.
- Reports select animals by current/as-of attributes and historical presence/activity, then preserve their entire financial lifetime. Missing purchase prices remain unknown; farm-born explicit zero is complete. Shared report templates are editable by any user and audited.
- Browser-local pending input is encrypted and account/session scoped. A generic public recovery shell supports offline reload, readable download/retry/discard. It never caches an offline farm database. Clearing storage/closing a session can lose local recovery input; committed events remain server-owned and idempotent.
- Daily consistent, encrypted archives are atomically published; keep the three latest successful unique versions. The optional NAS pull verifies immutable ID, size/checksum and transfer completion before local publication/rotation. Never put the private recovery key or credentials in Git.

## Development and tests

Use Python 3.13 and MariaDB 11.8; SQLite cannot validate this application's locks/constraints. Runtime artifacts and build tools have separate hash-verified locks. Test requirements are in `requirements-dev.lock`. See [test results](docs/testing/RESULTS.md) for executed commands and [isolated test helper](ops/test-isolated.sh) for a disposable Docker development lab. Docker is a developer-test tool only.

The suite exercises the complete overlapping April/August synthetic fixture and independent costs/P&L, correction branches, real-engine concurrency, browser loss/retry recovery, PDF/XLSX extraction and encrypted isolated restore. Generated artifacts under `docs/testing/generated/` contain **synthetic test records only**.

## Archive and review workflow

Legacy archive branch: `archive/legacy-desktop-2026-10-23`, exact commit `cf1c9c0244462d39a398875c7f8f228fde4a3deb`. Development branch: `rebuild/web-replacement`. Preserve the archive and all history; review through a draft pull request, never merge automatically. The original desktop source remains retrievable from the archive.

Preparation documents under `docs/rebuild/` are historical design records. Current implementation status and verification are in the linked operational/test documents; old unchecked preparation-stage boxes are not current status. The owner authorised replacement implementation, but **has not authorised connecting to or modifying the real VPS, NAS or live data**. All reported installation tests must identify their isolated environment and distinguish systemd boot/public certificate checks from static/service checks.
