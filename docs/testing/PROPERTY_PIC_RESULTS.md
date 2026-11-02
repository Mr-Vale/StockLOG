# StockLOG property/PIC upgrade validation

Environment: isolated Ubuntu 24.04 workspace, Python 3.12.14, Django 5.2.18. No VPS or NAS access. The disposable SQLite test settings are explicitly a functional fallback, not a supported production backend or proof of InnoDB locking/constraints.

Executed:

```sh
STOCKLOG_SECRET_KEY=development-only STOCKLOG_DEBUG=1 STOCKLOG_HTTPS=0 .venv/bin/pytest --ds=tests.settings_sqlite tests/test_properties.py tests/test_foundations.py tests/test_business_rules.py tests/test_web.py tests/test_nas_pull.py -q --tb=short -k 'not real_engine_constraints'
STOCKLOG_SECRET_KEY=development-only STOCKLOG_DEBUG=1 STOCKLOG_HTTPS=0 .venv/bin/pytest --ds=tests.settings_sqlite tests/test_acceptance.py -q --tb=short
STOCKLOG_SECRET_KEY=development-only .venv/bin/python manage.py check --settings=tests.settings_sqlite
STOCKLOG_SECRET_KEY=development-only .venv/bin/python manage.py makemigrations --check --dry-run --settings=tests.settings_sqlite
bash -n ops/install-debian13.sh ops/bootstrap-debian13.sh
node --check herd/static/herd/home.js
node --check herd/static/herd/mob-picker.js
python3 -m compileall -q herd tests
```

Functional suite: **37 passed, 1 production-engine test deselected**. The independent overlapping-cohort acceptance scenario also passed (1 test), including arithmetic, generated PDF/XLSX reconciliation, sales/deaths, feed/treatment costs and historical corrections. Raw outputs: [functional](property-pic-functional.txt), [acceptance](property-pic-acceptance.txt). Prior published report examples were retained; they are not presented as newly verified MariaDB outputs.

New tests cover first-admin setup without a property, atomic property/PIC creation, access revocation, malformed/cross-property selection, shared inventory across PICs, isolation from another property, saved defaults, a controlled 15-second deadline, stale forms and signed confirmations, chart boundaries/preferences, audited access changes and repurchase into another PIC with continuous identity/allocations.

## Outstanding verification

- This environment has no Debian 13/systemd test host or Docker. Fresh Debian installation, reboot persistence, real ACME issuance and public DNS checks were not executed.
- MariaDB packages could not be installed in this workspace. MariaDB 11.8 constraints, concurrency and encrypted database backup/restore still require the existing Debian isolated CI suite.
- Chromium download failed with a truncated archive. The remote browser cannot reach the local Django server (its loopback endpoint returns a bearer-token gateway error). Therefore no new desktop/mobile screenshots or live JavaScript browser results are claimed here.
- A browser test now covers selection, the controlled client timer and desktop/mobile screenshots. The existing PR workflow runs Debian/MariaDB/Chromium and uploads screenshots/reports under the `synthetic-acceptance-reports` artifact. Review those results before merging or installing.

The installer command is implemented and shell-validated, but is **not yet verified end-to-end on clean Debian 13**. Keep the PR in draft until production-engine and browser CI checks are reviewed. This release deliberately replaces the initial schema: do not apply it to a populated StockLOG 1 database.
