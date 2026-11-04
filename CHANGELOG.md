# Changelog

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
