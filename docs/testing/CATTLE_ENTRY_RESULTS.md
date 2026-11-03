# UI and cattle-entry verification

Implemented from current `main` at `e6cfa072913c8c85f4b06516100dfe56db13b992` on `feat/cattle-entry-and-navigation`. All animals, accounts and properties used below are synthetic. Tests used disposable Debian 13/MariaDB containers and portable SQLite functional checks; no VPS/NAS or running installation was contacted.

## Executed checks

| Command / environment | Actual result |
|---|---|
| `/opt/test-venv/bin/pytest tests -q --junitxml=docs/testing/cattle-entry-junit.xml` in isolated Debian 13, Python 3.13, MariaDB | **71 passed in 103.04s**; full financial, inventory, treatment, lifecycle, audit, backup/restore, browser, import and concurrency suite |
| `/opt/test-venv/bin/python manage.py makemigrations --check --dry-run` | No changes detected |
| `/opt/test-venv/bin/python manage.py check` | No issues |
| `/opt/test-venv/bin/pytest tests/test_cattle_entry.py tests/test_entry_browser.py -q --junitxml=docs/testing/cattle-entry-focused-junit.xml` in MariaDB container, after final mob review and retry refinements | **24 passed in 21.16s** |
| `pytest --ds=tests.settings_sqlite tests/test_cattle_entry.py tests/test_entry_browser.py -q` after final UI wording/styling and screenshot updates | **24 passed in 21.88s**; this final run includes the additional named-mob review regression added after the full-suite run |
| `ruff check --no-cache herd/active.py herd/entry.py herd/services.py herd/middleware.py tests/test_cattle_entry.py tests/test_entry_browser.py tests/test_concurrency.py` | All checks passed |
| `git diff --check` | Passed |
| `ops/test-installer.sh` against a fresh disposable Debian 13 container, using a copied source tree and a read-only session CA mount with `PIP_CERT` | Passed initial administrator/empty-property setup, service-user Caddy validation, root:caddy:0640 assertions, private environment readability rejection, deployment error-level check, and refusal to reinstall |

The initial dependency attempt lacked host MariaDB headers; production-engine checks then used the repository's locked dependencies inside Debian 13. Initial implementation runs exposed a homepage template typo and an invalid-length synthetic concurrency tag; both were fixed before the passing runs. An installer attempt stopped at its unchanged 1 GiB disk guard; removing only this task's disposable test image/container allowed the fresh run to pass. No guard was bypassed. Installer deployment checks retain the existing three non-fatal security warnings (CSP supplies frame protection; HSTS subdomain/preload choices remain operational settings).

The full-suite result predates one additional named-mob review test; the final focused run covers that test and the final UI. The MariaDB suite includes two-session conflicting stock, same-key submission retry, and competing animal-entry tests. Five-second transition tests use mocked server time and the controllable browser clock; they do not wait five seconds in real time.

## Coverage

- Saved vs temporary selection, restored compact card, Change selection expansion, server deadline, old forms, current selection scoping, first property/admin access, chart boundaries and layout ordering.
- Sidebar order/administrator visibility/current-page state, mobile collapse, title-bar destination and responsive content; reduced-motion spinner remains stationary without removing destination or server pause.
- Exact active columns, ascending/descending sort controls and comparisons, separate zero-prefixed identifiers, current entry periods, lifetime costs and unknown totals, sex mapping, DOB/estimated/farm-residence ages, and overlapping/superseded/reversed restriction dates.
- Purchase/Birth/Re-Purchase field sets; optional mother/DOB; locked birth source and zero cost; RFID or visual mother metadata; date permissions, impossible chronology and both DST transitions; account date preference in review.
- Multiple staged rows, mode retention, editing/removal, named PIC mobs, final atomic rollback, row errors with preserved input, permanent historical tag reservations/conflicting links, same-PIC repurchase history, active/other-PIC rejection, stale-context blocking/restart, concurrent identity entry, exact submission retries including a next-day retry, and unchanged import review.

## Screenshots

Captured with real headless Chromium at 1440 × 1000 and 390 × 844, using an Australian browser locale and synthetic data. Screenshots include the full page; the mobile cattle table scrolls horizontally inside its container.

| Screen | Desktop | Mobile |
|---|---|---|
| Homepage | [View](cattle-entry-screenshots/desktop-home.png) | [View](cattle-entry-screenshots/mobile-home.png) |
| Active Cattle | [View](cattle-entry-screenshots/desktop-active.png) | [View](cattle-entry-screenshots/mobile-active.png) |
| Purchase | [View](cattle-entry-screenshots/desktop-purchase.png) | [View](cattle-entry-screenshots/mobile-purchase.png) |
| Birth | [View](cattle-entry-screenshots/desktop-birth.png) | [View](cattle-entry-screenshots/mobile-birth.png) |
| Re-Purchase | [View](cattle-entry-screenshots/desktop-re-purchase.png) | [View](cattle-entry-screenshots/mobile-re-purchase.png) |
| Populated review list | [View](cattle-entry-screenshots/desktop-review.png) | [View](cattle-entry-screenshots/mobile-review.png) |

## Explicit limits and lifecycle decision

[Implementation notes](../CATTLE_ENTRY.md) document local-midnight timestamp conversion, the date-only forms' administrator requirement for historical dates, the signed temporary list, unknown acquisition costs, and the removal of cross-PIC Re-Purchase. No automatic or newly invented transfer workflow exists. Bulk Import remains Purchase only. Re-Purchase acquisition cost is unknown until completed through existing cost correction tools.

Lists are temporary signed browser input, expire after 24 hours and are not a permanent draft system. A destination generation change requires an explicit restart. Public ACME, PID-1 boot/reboot and actual VPS deployment were not attempted. No merge, deployment, data wipe or server reinstall occurred.
