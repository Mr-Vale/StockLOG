# Inventory selection, product details and currency display

Base main: 1180027b054577e06e4664ab7f98027716f304d1 (0.4.0).
Read root AGENTS.md, README, release policy, specifications, property/PIC rules,
Active Cattle's server sorting and signed selections, inventory forms/services,
reversals, reports and existing tests. There are no nested AGENTS instructions.

## Behaviour and compatibility

No schema changes. Property-wide inventory, immutable receipt specifications,
stock postings, historical feeding cohorts/costs and Decimal precision are
retained. Feed enquiries reuse Active Cattle's layout, sortable links, arrow and
aria-sort conventions. All ten columns sort by typed values; Batch/Date sorts
chronologically then by batch, with missing dates last. Selection uses product IDs,
preserved in sort links, and signed actor/context/action-bound tokens. The server
checks eligibility before form display, preview and save. Confirmation runs under
the existing property lock with version checks and exact idempotent retries.

Product and bulk edits expose the existing actual stock balance, retirement and
reason controls. Remove Feed supports both stock correction and retirement,
as confirmed by the user: an unchanged balance retires without a deduction;
a smaller actual balance records a stock adjustment. It cannot increase stock.
Each product requires a reason. No correction reallocates historical cattle costs.
The user also requested the note: “To change the price, retire this product, then
add it again with the new price.” Receipt price/size and frozen cost basis remain
unchanged; a new price is a new receipt specification.

Stock entry/holding figures are property-wide. Feeding statistics follow the
existing Event property/PIC scope, use event participants (or recorded feed
allocations for older cohorts), and exclude reversed feedings. Cattle are counted
once across events. Missing cohorts or stock movements produce Not recorded;
current mob membership is never used to reconstruct missing history. No feedings
gives zero cattle/quantity and no latest date.

Currency wording is presentation-only: $ replaces explicit currency codes/names.
Report datasets, export amounts, stored audit payloads and calculations are not
converted. Feed table/preview rounding uses Decimal HALF_UP to at most two places,
then strips trailing zeroes. It never changes form input, signed payloads or saved
values. Price, stock and feeding calculations keep existing precision.

## Release and verification

0.5.0 is a minor bump for compatible selection/detail features from 0.4.0.
Version and changelog updated. No migrations, dependencies, production service or
updater changes. Main/version and the unused v0.5.0 tag need rechecking before
approved merging. Merge, release publication and deployment remain separate.

The execution workspace is unavailable; implementation uses GitHub tools and
verification runs in isolated GitHub Actions Debian/MariaDB/Chromium jobs.
Functional tests cover typed sorting, selection scope/tampering, empty selections,
one/multiple edits, no-write previews, precise saves, stale previews/retries,
removal/reversal, historical usage/membership changes, missing records and
currency labels. Chromium checks the ten headers/arrows, selection retention
through sorting, disabled actions, product edits, tabular previews, removal and
1440/390px layouts. Screenshots are uploaded under feed-inventory in the
synthetic-acceptance-reports artifact. Final CI results are recorded in the PR.
No local/manual browser execution is claimed.
