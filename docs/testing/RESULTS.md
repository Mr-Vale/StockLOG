# Executed validation — 23 October 2026

All data and credentials used below are synthetic. No owner VPS, NAS, live database or NLIS service was contacted. The three supplied source files remain byte-for-byte unchanged against `docs/rebuild/evidence/supplied-files.json`.

## Final application suite

The final suite runs against real MariaDB, not SQLite. Command inside the isolated Debian 13 development container:

```sh
export STOCKLOG_SECRET_KEY=isolated-test-key-only STOCKLOG_DEBUG=1 STOCKLOG_HTTPS=0
python manage.py makemigrations --check --dry-run
ruff check herd stocklog tests ops manage.py
pytest -v --junitxml=docs/testing/generated/junit.xml
```

**Final result: 37 passed, zero failed, in 82.81 seconds.** Migration drift and Ruff checks also passed.

The checked-in [console result](generated/full-suite.txt) and [JUnit result](generated/junit.xml) record the executed count and outcome. Python 3.13.5, Django 5.2.18, MariaDB 11.8.6 and actual Debian Chromium were used. The lab was limited to two CPUs and 2 GiB RAM. Django debug/plain HTTP settings above apply only to the isolated test server; the installed production settings were independently tested over HTTPS.

Coverage includes all 13 acceptance correction branches: identifier uniqueness/nonreuse; replacement tags; role/time-limited compensation; feed boundaries/fractions; atomic chemical shortage and unit/expiry checks; historical membership and cost/restriction adjustments; browser offline reload/download/retry and lost commit; two real database-session races; exits/restriction acceptance/repurchase; incomplete purchase price and farm birth; lifetime filters/templates/exports; receipt matching/retirement/stocktake; ten-year retention and encrypted restoration. Additional regression cases cover same-second ordering, per-purchase-cycle corrections, last-admin protection, stale confirmations, CSRF, bounded CSV/XLSX imports and exact compensation subtotals.

The complete cohort integration fixture uses ordinary service permissions, a controlled clock, Melbourne calendar days and interleaved April/August events. The August fixture replenishes in two-bag increments to meet the supplied explicit 1,040 kg receipt total. This is a test scheduling assumption, not a minimum refill rule in the application.

| Cohort | Cost AUD | Revenue AUD | Lifetime profit AUD |
|---|---:|---:|---:|
| April, including two deaths | 10,818 | 20,000 | 9,182 |
| August, including four deaths | 21,636 | 40,000 | 18,364 |
| Combined | 32,454 | 60,000 | 27,546 |

April survivor profit is 9,525; April deaths total −343. There are 36 original animals, six deaths and 30 sales. Milk remainders are 17.4/34.8 kg; chemical remainders 50/0 mL. Assertions independently verify per-animal allocations, inventory and financial totals. [Machine-readable reconciliation](generated/reconciliation.json) and [permanent fixture identities](generated/fixture-identities.json) accompany the exports.

## Generated exports and browser evidence

- [April original mob PDF](generated/A-mob-lifetime.pdf) and [Excel](generated/A-mob-lifetime.xlsx).
- [April survivors PDF](generated/A-survivors.pdf) and [Excel](generated/A-survivors.xlsx).
- [August original mob PDF](generated/B-mob-lifetime.pdf) and [Excel](generated/B-mob-lifetime.xlsx).
- [August survivors PDF](generated/B-survivors.pdf) and [Excel](generated/B-survivors.xlsx).
- [390-pixel phone browser](generated/phone-animals.png) and [desktop report browser](generated/desktop-reports.png).

Tests extract PDF text and XLSX values, verify totals, required LPA section fields, formula-injection protection, full-precision accounting and grouped compensation. A rendered April PDF and responsive phone screenshot were also visually inspected. The supplied workbook is a field reference, not a pixel-perfect form reproduction; supported sections are 2, 3C, 3D, 5A, 5B and 6. Weight/NVD totals requiring owner knowledge are explicitly marked supplied overrides, not invented measurements.

## Clean native installer and recovery

[Installed-stack evidence](generated/installed-stack-results.json) records a separate clean Debian 13 container, also limited to two CPUs/2 GiB. The native installer installed its own OS/build/runtime packages, created accounts/configuration/persistent directories, applied migrations and validated Caddy. A repeat run preserved existing configuration, recovery-key checksums and the existing synthetic administrator.

The installed Caddy → unprivileged Gunicorn → Django → MariaDB path passed authenticated HTTPS sign-in, secure-cookie/no-store checks, health and static-file routing. TLS verification used Caddy's explicitly trusted local test CA; verification was never disabled. Installed `stocklog-manage backup` produced an encrypted archive; the native restore script restored into a new empty schema while retaining the source. Ordered logical row dumps of **every table** matched exactly. The actual restricted backup-reader OS account could read only the published protocol and retrieve a ciphertext with matching SHA-256. Systemd unit files passed `systemd-analyze verify`.

The application suite separately tests archive rotation to the latest three unique successful versions, failed-publication safety, isolated restore including account/settings/template/audit/business state, and NAS pull checksum/temporary-file/failure/duplicate behavior through a local fake SSH transport. The NAS tests do not connect to a NAS.

`ops/test-isolated.sh` was also executed successfully from a fresh disposable Debian lab during implementation. It provisions database/browser/build prerequisites and runs the suite; the final suite was rerun after subsequent regression additions. `.github/workflows/tests.yml` runs this helper, but no successful remote GitHub Actions execution is claimed.

## Explicitly unverified and operational limits

- Real systemd PID-1 boot/reboot and service/timer restart behavior: not executed in this container lab. Units were statically validated and service processes exercised manually.
- Public DNS, port reachability and ACME certificate issuance: not tested; local HTTPS used Caddy's internal CA.
- Owner VPS installation, actual NAS SSH/key/scheduler behavior, real production data migration and external notifications: not performed. No automatic legacy-data migration is included; production starts empty.
- Long-running production capacity, full 33 GB disk pressure, multi-year operational load and real-time backup monitoring are not established by this synthetic suite. Monitor growth and failed timer runs.
- Restore compatibility is explicitly checked for this application/schema version. Arbitrary later-version restores and automatic database-downgrade rollback are not promised.

Before real records: follow [installation](../operations/INSTALL.md), verify public HTTPS/systemd restart/backup, preserve the private recovery key off-server, and perform an isolated recovery drill. Configure NAS access only when separately authorised.
