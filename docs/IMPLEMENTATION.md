# Replacement implementation checklist

Implementation authorised by the owner on 23 October 2026. Native Debian 13 + Caddy + Gunicorn + Django + MariaDB is the sole production approach. HostGator/cPanel, Python 3.9, MySQL 5.7 and Docker deployment constraints are explicitly superseded. Docker may be used only for isolated test infrastructure. Legacy archive: `archive/legacy-desktop-2026-10-23` at `cf1c9c0244462d39a398875c7f8f228fde4a3deb`.

- [x] Framework, hash-locked dependencies, MariaDB migrations, account/property scope, permanent identities, temporal and ledger models.
- [x] Initial transactional service layer, safe first-admin command, server-rendered workflow forms and account security boundaries.
- [ ] Complete animal/import/lifecycle/mob workflow validation and domain tests.
- [ ] Complete inventory/feed/treatment/procedure/correction/concurrency validation.
- [ ] Complete reports/LPA coverage, browser recovery, permissions and browser tests.
- [ ] Complete native clean-Debian installer, systemd/Caddy configuration, encrypted backup/NAS pull and isolated restore validation.
- [ ] Full two-cohort acceptance fixture, all correction branches, generated PDF/XLSX and independent reconciliation.
- [ ] Operational documentation, actual test evidence, branch publication and draft PR.

Checks and remaining limitations will be updated with actual executed results; a checked implementation item is not a claim that a VPS deployment occurred. The owner's VPS/NAS/live data must not be contacted.
