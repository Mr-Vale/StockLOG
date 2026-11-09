# Changelog

## 0.2.4

Refine the combined animal detail page with labelled NLIS identifiers, actions
above responsive summary cards, and an Edit Animal form collapsed by default.
Keep editing open for validation errors and preview/confirmation. Always show
the Farm exit card, with an empty body for active animals.

Compatible UI patch from 0.2.3; no database migrations, dependency changes or
reinstall required. Existing permissions, records and save/history workflows
are preserved.

## 0.1.0

First versioned release of the current property/PIC application. Adds Settings
version display, exact commit identification, stable tagged installation and
backup-first compatible updates with health checks and conservative recovery.
Existing unversioned installations require explicit administrator assessment;
the updater never guesses their version or schema compatibility.

## 0.2.1

bulk edits and cattle exit updates

Fix the updater confirmation prompt on non-seekable terminals by opening terminal
input and output separately.
