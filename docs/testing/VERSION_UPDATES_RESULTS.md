# Versioning and update validation — 4 November 2026

No live server, production database, published release, merge or tag was changed.
There were no AGENTS.md files in the repository or its workspace ancestors.

## Automated checks

- Existing Debian 13 / MariaDB / Chromium suite: **92 passed** in 289 seconds.
- Focused release and Settings/web checks: **26 passed**. Includes an actual local
  Git repository with a stable tag followed by a newer main commit; the resolver
  deployed the tagged commit, never the newer main commit.
- Python lint, Python compilation, shell syntax and whitespace checks passed.

`ops/test-installer.sh` installs Debian 13 packages/schema/dependencies in a
fresh disposable container, exercises domain/admin terminal prompts and Caddy
service-user permissions, and then runs `ops/test-updates.py`. Its synthetic
published release fixtures avoid publishing test releases into the real repo.
The updater itself runs real dependency preparation, MariaDB migrations, age
backup/decryption/checksum validation, static publication, symlink activation and
Gunicorn restart. A service adapter substitutes for systemd PID 1, and health
checks use the real local HTTP/database/version/commit response.

**The Debian installer/update matrix passed.** It covers current/no-change, patch and minor deployment, blocked major,
failed download, simultaneous update locking, compatible health-failure rollback,
and changed-migration health failure with rollback blocked and the app stopped.
It checks retained records, administrator password, standard-user password and
property access, property/PIC configuration, environment/secrets, domain/Caddy
settings, backup timer and pinned encrypted recovery copies.

## Practical limits

This is a fresh Debian 13 **container** installation with `--no-start` followed by
real manually supervised Gunicorn processes. It does not prove systemd boot,
reboot recovery, public DNS/ACME issuance or public HTTPS health from a real host.
Those require a separate disposable server/domain rehearsal before production.
No such target was supplied or altered. Production code checks both local HTTP
and public HTTPS and requires the expected version/commit before success.

The full 92-test suite completed before the final additional real-Git resolver
case; that case and the complete focused set passed separately afterward.
GitHub currently has no published releases. End-to-end production release
selection therefore cannot complete until a reviewed stable tag/release is
published. Missing releases fail closed. Unit/local-Git tests cover release
validation, prerelease/draft rejection, tag/version mismatch and exact tag fetch.
