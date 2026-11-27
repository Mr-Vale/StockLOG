# Changelog

## 0.4.0

Separate property-wide Feed Inventory and Chemical Inventory pages. Add a reviewed
feed entry form with whole-number receipt quantities, source/testing details and
compatible item/feed units. Add date-only cattle feeding with positive-stock/type
filters, whole-item or measured quantities, negative-balance previews, and atomic,
idempotent stock/cost/audit confirmation. Feed removal retires records; bulk
balance corrections preserve historical costs.

Compatible feature release from 0.3.0. Additive migration 0002 adds an optional
feed_unit column; existing inventory IDs, balances, cost bases and historical
links remain unchanged. Legacy items use a compatible unit fallback. No reinstall
or dependency/service changes. Migration changes mean the updater's conservative
rollback guard may require forward recovery after an activation failure.

## 0.3.0

Select cattle on Active Cattle before Bulk Edit or Cattle Exit. Carry an exact,
context-bound selection into the form and recheck eligibility when saving.
Bulk Edit now supports Update Mob, with each Update control grouped with its
field. Bulk and exit previews, restriction warnings and confirmations remain.

Individual animal edits save directly with existing validation, field permissions
and audit logging. Cattle entry confirmation links use matching dark green
buttons and include Return to Active Cattle.

Compatible feature release from 0.2.4; no schema, dependency or service changes,
and no reinstall required.

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
