# StockLOG property/PIC upgrade validation

No owner VPS or NAS was accessed. Application changes were tested locally and in a disposable GitHub CI Debian 13 container.

## Production-engine and browser suite

[GitHub run 41439761804](https://github.com/Mr-Vale/StockLOG/actions/runs/41439761804) passed **all 47 tests** on Debian 13, Python 3.13.5, Django 5.2.18, MariaDB and Chromium. [Run 41439959975](https://github.com/Mr-Vale/StockLOG/actions/runs/41439959975) repeated the acceptance job successfully after adding the separate installer job.

Coverage includes:

- Real-engine identity constraints, transaction idempotency and concurrent feed/chemical deductions.
- Full independent overlapping-cohort acceptance scenario, PDF/XLSX arithmetic and historical correction reconciliation.
- Encrypted backup rotation/failure handling and restoration into a separate empty database. Restored values are compared for accounts, property access grants, PICs, presence cycles, cattle, inventory, events, allocations, audit and shared templates.
- First-admin creation without a property; atomic property/PIC creation; property grants/revocation; wrong-PIC/cross-property rejection and shared property inventory.
- Saved defaults, stale forms and signed confirmations, a controlled server/client transition (originally 15 seconds; now 5 seconds, see CATTLE_ENTRY_RESULTS.md), chart boundaries/preferences and mob retirement/undo.
- Four Chromium tests covering login, mobile registration, exports, offline loss/retry recovery, account separation, context selection, a controlled client timer and desktop/mobile layout without horizontal overflow.

Raw CI test lines: [47-test output](property-pic-ci.txt).

Screenshots were retrieved from the passing CI artifact, visually inspected and saved in the repository:

- [Selection screen](../../example-pages/property-selection-desktop.png)
- [Populated desktop homepage](../../example-pages/property-home-desktop.png)
- [Populated mobile homepage](../../example-pages/property-home-mobile.png)

The initial CI run had 46 passes and one obsolete test assertion expecting backup schema 1 after the deliberate bump to 2. The assertion was corrected and restore checks expanded; the follow-up run passed all 47 tests. No application business-rule tests were bypassed in CI.

## Local checks

Local environment: Ubuntu 24.04, Python 3.12.14, Django 5.2.18. SQLite settings are a portable functional fallback, not a production backend or substitute for InnoDB verification.

```sh
STOCKLOG_SECRET_KEY=development-only STOCKLOG_DEBUG=1 STOCKLOG_HTTPS=0 .venv/bin/pytest --ds=tests.settings_sqlite tests/test_properties.py tests/test_foundations.py tests/test_business_rules.py tests/test_web.py tests/test_nas_pull.py -q --tb=short -k 'not real_engine_constraints'
STOCKLOG_SECRET_KEY=development-only STOCKLOG_DEBUG=1 STOCKLOG_HTTPS=0 .venv/bin/pytest --ds=tests.settings_sqlite tests/test_acceptance.py -q --tb=short
STOCKLOG_SECRET_KEY=development-only .venv/bin/python manage.py check --settings=tests.settings_sqlite
STOCKLOG_SECRET_KEY=development-only .venv/bin/python manage.py makemigrations --check --dry-run --settings=tests.settings_sqlite
bash -n ops/install-debian13.sh ops/bootstrap-debian13.sh ops/test-installer.sh
node --check herd/static/herd/home.js
node --check herd/static/herd/mob-picker.js
python3 -m compileall -q herd tests
```

Local functional suite: **37 passed, 1 production-engine test deselected**; independent acceptance scenario: **1 passed**. Raw outputs: [functional](property-pic-functional.txt), [acceptance](property-pic-acceptance.txt). System, migration-drift, Python/JS/shell syntax and whitespace checks passed. The installer also correctly refused this Ubuntu host before making installation changes.

Chromium downloads and local MariaDB package installation were blocked locally; GitHub CI supplied the real-engine/browser verification instead. Prior report examples under `generated` are retained as earlier artifacts; use the linked CI run for current generated reports and XML results.

## Installer and remaining server checks

A separate `installer` CI job runs `ops/test-installer.sh` in a fresh Debian 13 container. It drives domain/username/hidden password prompts through a pseudo-terminal, installs packages/dependencies, creates the empty schema and initial administrator, runs deployment checks and verifies that rerunning refuses an activated installation. **This installer job passed in run 41439959975.** Package/dependency installation, schema creation, hidden password prompts, Caddy configuration validation, administrator authentication and rerun refusal all completed successfully. A test-only PTY closure delay was identified and shortened after this run; application/installer code was unchanged.

This test uses `--no-start`: it cannot verify systemd as PID 1, reboot persistence, public DNS routing or real ACME certificate issuance. Those checks remain for a real isolated server/VM. The installer implements service enable/start and local/public health checks, but no full public-server installation is claimed here.

This release is fresh-install only. Its regenerated initial migration and schema-2 restore format must not be applied over a populated StockLOG 1 database.
