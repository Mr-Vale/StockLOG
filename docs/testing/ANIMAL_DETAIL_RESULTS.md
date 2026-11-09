# Combined animal detail/edit verification — 9 November 2026

Implemented from `main` at `b1ec6cc` on `feat/animal-detail-edit`. No applicable
`AGENTS.md` was present. Reviewed the current rebuild specification,
`docs/IMPLEMENTATION.md`, `docs/PROPERTY_PIC.md`, cattle forms/services, model,
report allocation rules, HTTP context boundary and existing cattle/property tests.

The animal URL used by Active Cattle now renders its summary followed by the
existing edit/preview/confirmation workflow. Older Edit Animal links redirect to
this URL. Successful edits return to the animal's stable UUID URL, including an
identifier change. Departed animals remain locked against ordinary editing.
The separate history URL checks the same animal/property/PIC boundary before
showing identifier lineage and lifetime events. No models, mutation services,
financial records or retention rules changed.

The summary uses the existing report's full lifetime cost calculation, including
correction/compensation allocations, and explicitly flags unknown costs. Entry
source information uses existing acquisition/correction logic, including PIC
transfers and repurchases. Sale price comes from this animal's allocation for
its latest departure, including group sales and valid zero proceeds. Farm births
and deaths explain which source/exit fields do not apply. Applicable gaps say
`Not recorded`.

## Executed checks

Synthetic records only, in the existing isolated Debian 13 Docker development
lab (`stocklog-lab`): Python 3.13.5, Django 5.2.18, MariaDB 11.8 and real headless
Chromium. No VPS, NAS or live data access. Local HTTP/debug settings were used:

```sh
export STOCKLOG_SECRET_KEY=isolated-test-key-only STOCKLOG_DEBUG=1 STOCKLOG_HTTPS=0
python manage.py makemigrations --check --dry-run
ruff check herd/animal_details.py herd/cattle.py herd/views.py herd/urls.py \
  tests/test_animal_detail.py tests/test_animal_detail_browser.py tests/test_cattle_changes.py
pytest tests/test_animal_detail.py tests/test_animal_detail_browser.py \
  tests/test_cattle_changes.py tests/test_cattle_browser.py tests/test_properties.py \
  tests/test_web.py -v --junitxml=/tmp/animal-detail-junit.xml
```

Migration drift: none. Ruff on changed Python files: passed. Relevant suite:
**54 passed in 30.18 seconds**.

New regressions verify missing source/identity fields, unknown and zero costs,
preview rollback, saved summaries, administrator and standard-user field controls,
role/access revocation, wrong property/PIC and purged-animal denial, signed animal
and context binding, stale preview recovery, identifier history, latest treatment
and reversal, current acquisition after transfer/repurchase, per-animal group-sale
proceeds, birth/death applicability and the exact Active/Deactive labels.

The browser regression opens the animal from Active Cattle, fills a source-name
gap, previews/confirms, verifies the same URL and updated summary, opens the
selected animal's history and checks the recorded correction. It compares computed
homepage, Preview changes and View lifetime history styles (colour, typography,
padding, margin, corners and outline) in normal, hover and keyboard-focus states.
[Desktop (1440px)](animal-detail-screenshots/desktop.png) and
[mobile (390px)](animal-detail-screenshots/mobile.png) screenshots were visually inspected; no
horizontal overflow. It also renders a completed sale with zero proceeds.

An initial disposable-lab run exhausted disk after an extra test image was
created. That image was removed; the clean rerun above used the existing lab.
The initial interrupted run is not counted as successful validation.

## Full suite

`pytest -v --junitxml=/tmp/animal-detail-full-junit.xml`: **136 passed, 1 failed
in 100.24 seconds**. The sole failure was the unchanged
`tests/test_release_updates.py::test_confirmation_with_nonseekable_terminal[-False]`:
the PTY read returned only the echoed newline before the expected prompt. Neither
that test nor `ops/update.py` differs from the base branch. A focused recheck of
`pytest tests/test_release_updates.py -v` passed **all 24 tests in 0.12 seconds**.
This is an intermittent terminal-output assertion; it was not changed in this
animal-page PR. The full run passed accounting acceptance, encrypted restore,
concurrency, offline/browser recovery and all animal-page tests.
