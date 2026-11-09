# Animal detail layout refinement — 9 November 2026

Based on current `main` at `9b67ae3`, on `fix/animal-detail-layout`.
Read the root `AGENTS.md` (no nested instructions), README, release/update policy,
and the existing combined-page template, styles, workflow and tests.

## Behaviour and review evidence

- Visible NLIS Visual ID and NLIS RFID labels precede the animal actions.
- Actions keep their existing order, URLs and shared homepage button styles.
- Four summary cards share the available desktop width and stack on mobile.
  Applicable missing values remain `Not recorded`; status stays Active/Deactive.
- Farm exit is always present. Active animals have a title and empty card body;
  departed animals retain the existing exit fields and applicable sale price.
- Native HTML `details` keeps Edit Animal collapsed on an ordinary page load and
  expands it in place without JavaScript. Bound submissions, workflow errors and
  confirmation previews render it open. Successful saves return to the same
  animal URL with the saved summary and a collapsed editor.
- Existing fields, server permissions, calculations, mutation services, audit
  events and on-demand history are unchanged.

Synthetic browser evidence, visually inspected at 1440px and 390px:

| State | Desktop | Mobile |
| --- | --- | --- |
| Active, missing values, collapsed edit | [Screenshot](animal-detail-screenshots/desktop.png) | [Screenshot](animal-detail-screenshots/mobile.png) |
| Departed, populated exit card | [Screenshot](animal-detail-screenshots/desktop-exited.png) | [Screenshot](animal-detail-screenshots/mobile-exited.png) |

The Chromium regression checks the identifier labels, action order and position,
card alignment/stacking, empty and populated exit bodies, no horizontal overflow,
collapsed/expanded editing, retained values after a field error, preview/confirm,
save/audit and selected-animal history. It continues comparing action button
styles against the homepage in normal, hover and keyboard-focus states. HTTP
regressions cover field errors, invalid confirmations and stale previews staying
open, plus existing property/PIC/role checks and financial/history preservation.

## Version and compatibility

Proposed **0.2.4**, a patch increment from main's **0.2.3**. Under `AGENTS.md`
and `docs/operations/UPDATES.md`, this is a small compatible UI refinement of an
existing feature. It adds no business workflow or incompatible change requiring
a minor or major increment. Version file and changelog both include 0.2.4.

No migration files, pinned runtime dependencies, installer/updater files or service
configuration changed. No data migration or reinstall is required; the existing
compatible update path and rollback eligibility rules remain applicable. The
`v0.2.4` remote tag was unused during preparation. Before an approved merge,
recheck main's version and tag availability. Tagging the exact merged commit,
publishing a stable release, and deployment require separate approval. None was
performed. A real server update and public HTTPS/systemd checks were not run.

## Executed validation

Existing isolated Debian 13 Docker development lab `stocklog-lab`, Python 3.13.5,
Django 5.2.18, MariaDB 11.8.6 and real headless Chromium. Synthetic data only;
no live VPS, NAS or production records accessed.

```sh
export STOCKLOG_SECRET_KEY=isolated-test-key-only STOCKLOG_DEBUG=1 STOCKLOG_HTTPS=0
python manage.py makemigrations --check --dry-run
ruff check tests/test_animal_detail.py tests/test_animal_detail_browser.py
pytest tests/test_animal_detail.py tests/test_animal_detail_browser.py -x -v
pytest -v --junitxml=/tmp/animal-layout-junit.xml
```

Migration drift: none. Ruff on changed Python files: passed. Targeted tests:
**8 passed in 11.31 seconds**.

Full suite: **137 passed, 1 failed in 104.30 seconds**. The sole failure was the
unchanged `test_confirmation_with_nonseekable_terminal[y-True]` in
`tests/test_release_updates.py`: its PTY read saw only the echoed `y` before the
expected prompt. The same intermittent output-read issue was recorded in the
previous combined-page validation. Neither the test nor updater code changed.
Focused recheck: `pytest tests/test_release_updates.py -v` — **24 passed in
0.09 seconds**. The full run passed all animal-page tests, permission checks,
accounting acceptance, concurrency, encrypted restore and browser/offline checks.
