# Replacement implementation checklist

Implementation authorised by the owner on 23 October 2026. Native Debian 13 + Caddy + Gunicorn + Django + MariaDB is the sole production approach. HostGator/cPanel, Python 3.9, MySQL 5.7 and Docker deployment constraints are explicitly superseded. Docker may be used only for isolated test infrastructure. Legacy archive: `archive/legacy-desktop-2026-10-23` at `cf1c9c0244462d39a398875c7f8f228fde4a3deb`.

- [x] Framework, hash-locked dependencies, MariaDB migrations, account/property scope, permanent identities, temporal and ledger models.
- [x] Initial transactional service layer, safe first-admin command, server-rendered workflow forms and account security boundaries.
- [x] Animal/import/lifecycle/mob services and domain tests, including historical membership and tag nonreuse.
- [x] Inventory/feed/treatment/procedure/correction services and real MariaDB two-session stock/idempotency tests.
- [x] Complete reports/LPA coverage, browser recovery, permissions and browser tests.
- [x] Complete native clean-Debian installer, systemd/Caddy configuration, encrypted backup/NAS pull and isolated restore validation (container scope; actual systemd boot/public ACME remain unverified).
- [x] Full overlapping two-cohort lifecycle fixture and independent totals; generated PDF/XLSX for both original cohorts and survivor-only selections.
- [x] Browser recovery/phone/desktop evidence and operations/security checks for all 13 companion correction branches.
- [x] Operational documentation and actual test evidence.
- [x] Rebuild and legacy archive branches pushed; [draft PR #1](https://github.com/Mr-Vale/StockLOG/pull/1) opened against `main`. No merge or owner-host deployment performed.

Checks and remaining limitations will be updated with actual executed results; a checked implementation item is not a claim that a VPS deployment occurred. The owner's VPS/NAS/live data must not be contacted.

## Stage traceability

| Supplied stage | Implementation | Verification |
|---|---|---|
| Foundations/accounts | `stocklog/`, models/migrations, account forms and first-admin command | `test_foundations.py`, auth/CSRF/browser tests |
| Identity/lifecycle/import/mobs | `herd/services.py`, `imports.py`, registration/exit/mob workflows | business-rule, web and full-cohort tests |
| Stock/feed/treatment/procedures | transactional inventory and event allocations, per-event membership | boundary/shortage/history tests, real-engine concurrency |
| Finance/reports/LPA | `herd/reports.py`, saved shared templates, PDF/XLSX, audit rows | independent totals, all six LPA sections, compensation and formula checks |
| Recovery/responsive UI | encrypted pending input, public offline shell, same-submission retry | real Chromium phone/desktop and connection-loss tests |
| Operations/retention | `ops/`, encrypted backups, restricted NAS protocol, empty-target restore, ten-year purge | native isolated install/repeat, HTTPS, all-table restoration and backup/NAS tests |
| Acceptance/handover | unchanged supplied scenario and generated synthetic reports | [executed results and explicit limits](testing/RESULTS.md) |

Deployment is pending owner review, public hostname/DNS and off-server key custody. Local property time defaults to Australia/Melbourne; confirm it when configuring the property. NAS host/key/destination and monitoring delivery remain owner operational decisions. No additional business-rule decision blocks review of this implementation.
