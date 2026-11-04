# Cattle changes — verification results

Completed 5 November 2026 (Australia/Sydney) on branch `implementation/home-cattle-exit`, based on current main `ad4118e82bc1ef1e3fea61b602482dde99f1b0e6`.

## Production-engine suite

Command:

```sh
STOCKLOG_TEST_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt bash ops/test-isolated.sh
```

**126 passed in 368.53 seconds.** The repository harness created and removed its own disposable Debian 13 container with MariaDB, Python 3.13.5, Django 5.2.18 and Chromium, installing the existing hash-locked dependencies. All database accounts, credentials and animals were synthetic. No production service or database was contacted.

[Full pytest output](cattle-changes-mariadb.txt) · [JUnit results](cattle-changes-junit.xml)

Coverage includes administrator-only bulk editing and role revalidation, checked versus unchanged fields, intentional clearing/unknown costs, atomic corrections and audited reversal, current acquisition accounting across repurchase/transfer, populated/empty identifier permissions and a real two-session race, permanent reservations, new identifier patterns and unchanged legacy values, field layout and date-only forms, original age references, exact exit previews and stale mob/context rejection, withholding overlap/reversal/supersession, group-total reconciliation, same-property transfer and death/repurchase prevention. Existing financial, inventory, treatment, reporting, backup rotation/encrypted fresh-database restore, stock concurrency, browser recovery and release-update tests all pass.

## Other checks

- Portable focused run: `pytest tests/test_cattle_changes.py --ds=tests.settings_sqlite -q -p no:cacheprovider` — **31 passed**. SQLite is supplemental; MariaDB above is authoritative for locking and database constraints.
- Chromium responsive workflow: passed independently and in the full MariaDB suite. It checks 1440px desktop and 390px mobile layouts, form modes, retained values, bulk preview/save, selected-animal lists, populated sale preview and final save. No document-level horizontal overflow; Active Cattle has a scrollable table and its desktop main starts beside the 185px navigation.
- `python manage.py check --settings=tests.settings_sqlite` — no issues.
- `python manage.py makemigrations --check --dry-run --settings=tests.settings_sqlite` — no changes detected.
- Ruff checks of changed application modules and new/concurrency tests — passed.
- `bash -n ops/install-debian13.sh ops/test-installer.sh ops/test-isolated.sh` — passed. Static assertions confirm the existing `root:caddy` 0640 configuration permissions and `runuser` validation remain present. Installer files are unchanged.
- Supplied reference CSV scan: **57 rows; zero nonconforming supplied NLIS Visual, RFID, Source PIC or NVD values**. Existing synthetic placeholder identifiers in tests were updated to conform; no records were rewritten automatically.

## Screenshots and implementation notes

[Date handling, transfer and shared identifier validation](../CATTLE_CHANGES.md).

| Page | Desktop | Mobile |
|---|---|---|
| Homepage | [View](cattle-changes-screenshots/desktop-home.png) | [View](cattle-changes-screenshots/mobile-home.png) |
| Active Cattle | [View](cattle-changes-screenshots/desktop-active.png) | [View](cattle-changes-screenshots/mobile-active.png) |
| Bulk Edit | [View](cattle-changes-screenshots/desktop-bulk-edit.png) | [View](cattle-changes-screenshots/mobile-bulk-edit.png) |
| Edit Animal | [View](cattle-changes-screenshots/desktop-edit-animal.png) | [View](cattle-changes-screenshots/mobile-edit-animal.png) |
| Sale | [View](cattle-changes-screenshots/desktop-exit-sale.png) | [View](cattle-changes-screenshots/mobile-exit-sale.png) |
| Transfer | [View](cattle-changes-screenshots/desktop-exit-transfer.png) | [View](cattle-changes-screenshots/mobile-exit-transfer.png) |
| Death | [View](cattle-changes-screenshots/desktop-exit-death.png) | [View](cattle-changes-screenshots/mobile-exit-death.png) |
| Populated exit preview | [View](cattle-changes-screenshots/desktop-exit-preview.png) | [View](cattle-changes-screenshots/mobile-exit-preview.png) |

## Limits

No VPS deployment, production-data scan, merge, server reinstall or data wipe was performed. Live legacy identifier conformity is unknown; the new read-only `audit_identifiers` command is available for an authorised later scan. The full fresh-installer integration harness was not rerun locally; installer syntax/invariants were checked and the existing installer CI job remains enabled. Transfer simple reversal is unavailable; downstream occupancy requires a separately reviewed historical correction rather than a blind reversal. Existing dedicated Replace ear tag role rules remain distinct from Edit Animal's administrator-only changes to populated identifiers.
