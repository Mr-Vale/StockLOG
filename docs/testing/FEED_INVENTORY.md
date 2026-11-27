# Separate inventory and reviewed feeding

Base main: `2367c1080c5097ca0359f770a338bd42af202d17`. Read root AGENTS.md (the repository has
no nested instruction files), README, current specifications, property/PIC rules,
release/update policy, inventory models, receipt/feed/reversal services, forms,
views and existing regression suites.

## Schema and history

Retain the shared property-owned Inventory table and its existing feed/chemical
kind discriminator. Separate pages are views over those existing records, not
separate copies of stock. Additive migration 0002 adds a blank-default feed_unit
field. It does not change existing IDs, signatures, balances, base quantities,
prices, postings, allocations, events or audit links. Legacy feed uses its
compatible base/stock unit when no explicit feed unit is recorded.

New feed specifications include the chosen feed unit in receipt matching. An
equivalent legacy specification using the same effective unit refills the same
item without rewriting its signature or cost basis. Source
name/address, CVD and testing data remain on immutable receipt events, as in the
existing records; batch and typed expiry/DOM dates retain their existing columns.
No chemical fields or treatment contracts are repurposed. Removal retires feed;
bulk stock corrections use actual balances and never reprice past animal costs.
Those batch changes are audited, atomic and eligible for the existing reversal
rules.

## Transactions and context

Inventory remains shared across authorised PICs within one property. Mobs are
scoped to the selected property/PIC and eligible at the chosen feeding date.
Normal users retain earlier inventory/feeding date access; future business dates
are refused. Dates use the property calendar. Receipts use the stored date's
start; feeding uses the end of a past date or preparation time for today.

Feed receipts round package counts and sizes down before preview and save.
Duplicate positive-stock names are checked under the property transaction lock
for Add Feed. Legacy receipt/refill and stocktake tools remain available.
Mass and volume conversions are separate; no density conversion is invented.
Whole-item mode requires integers; measured quantities retain Decimal precision.
Legacy feeding modes and frozen historical quantities/cost bases are retained.

Existing services.preview rolls back all effects. Confirmation is actor/context/
operation bound and services.execute checks the exact idempotency digest, current
permissions and preview version under the property lock. Feeding also compares
reviewed balance/cost/size snapshots and the event-time cattle cohort. A positive
balance may cross below zero once; nonpositive products are absent from choices
and rejected by the service. A repeated confirmed save returns the original
result without a second deduction or allocation.

## Version and verification

Propose 0.4.0 from 0.3.0: compatible inventory/feeding features with a preserving
additive migration, no reinstall, runtime dependency or production service
changes. A changed migration means the updater's conservative automatic code
rollback guard may decline rollback after a failed activation; use the existing
forward-recovery process. Recheck main/version and unused v0.4.0 before approved
merging. No merge, release publication, deployment or live-data access is
performed.

The Cloud workspace is unavailable. Implementation uses the GitHub connector;
verification uses the repository's GitHub Actions isolated Debian/MariaDB/
Chromium acceptance and installer jobs. The test helper now checks migration
drift and Ruff for the new workflow module before running the suite. CI results
and screenshots will be linked in the PR. Browser evidence is written to the
synthetic-acceptance-reports artifact's feed-workflows directory. No manual local
browser inspection is claimed.
