# Implementation stages and requirements traceability

This task completes **preparation only**. No checkbox below implies application functionality exists. Stage numbering follows the supplied replacement prompt; the immediate next coding task is stage one after review. Source requirements remain in the unmodified [specification](../specifications/StockLOG_rebuild_agent_prompt.md), and synthetic assumptions/expected totals remain in the independent [scenario](../testing/StockLOG_acceptance_scenario.md).

## Preparation completed

- [x] Inspect existing checkout, available agent instructions and legacy structure.
- [x] Record full SHA and preserve legacy archive branch; verify complete-history recovery bundle.
- [x] Create `rebuild/web-replacement`; preserve every legacy application/configuration file.
- [x] Read and store all three supplied files byte-for-byte with SHA-256 evidence.
- [x] Inspect all workbook sheets/fields, hidden support data, formulas and drawing labels.
- [x] Verify maintained framework/runtime compatibility from upstream evidence; run isolated library probes.
- [x] Produce proposed architecture, logical database, included LPA field matrix and staged checks.
- [ ] Verify actual hosting account capabilities. External evidence is needed; do not confuse cloud probes with hosting checks.
- [ ] Owner reviews proposed stack, implementation policies and stage-one coding scope.

No production deployment, NAS connection, live-data change, replacement code, database migration, production dependency lock or paid purchase is included in preparation. No new environment configuration draft was published or silently replaced; the previous PyQt onboarding setup remains legacy-only and must be revised when the replacement is implemented.

## Stage one: foundations to implement after review

1. **Resolve target runtime**: obtain non-secret hosting evidence per [preflight](runtime-hosting.md). Confirm supported Python (recommend 3.12 latest patch), WSGI application mechanism and actual maintained InnoDB engine. Python 3.9-only hosting is an upgrade/change prerequisite. Resolve mysqlclient's client-library requirements on cloud and host without assuming host root access. Choose exact supported patches and record source citations/date.
2. **Establish the new project in this repository**: modular Django project alongside legacy initially, isolated settings and example non-secret configuration, local MariaDB/MySQL development/test workflow, hash-verified dependency locks, static asset layout, WSGI adapter. Keep the archive untouched. Do not delete old `App/` as part of foundation setup; replacement/removal requires the later authorised coding scope. No host deployment is needed for this coding milestone.
3. **Create versioned initial migrations**: property/account/settings, permanent identities/identifier reservations, temporal presence/membership structure, events/participants, inventory/financial/audit ledgers and idempotency foundations. Split migrations by domain/dependency rather than one opaque schema blob. Include the LPA fields in the model design before implementing forms. Rebuild an empty disposable production-engine database from migrations and verify FK/check/unique/collation behaviour directly.
4. **Implement safe authentication and administration boundary**: no public registration; maintenance-only first-admin creation with no default secret; admin account creation/reset/disable; protect last admin; two-role server checks, session/CSRF/cookie settings and property scope. Do not equate phone/desktop layout with authorisation. Protect model admin from direct business mutation.
5. **Implement shared transaction primitives**: injected server clock, Unix time/order conversion, property mutation guard, Decimal conversion and deterministic allocation utility, append-only audit service, idempotency commit/result protocol. Define preview/version checks before later domain services depend on them. Keep mutation tests on real InnoDB and separate schema test helpers from ordinary-user workflows.
6. **Deliver stage-one evidence**: migration replay, direct invalid insert rejection, authenticated/unauthenticated and CSRF tests, role boundaries/last-admin tests, exact decimal residual tests, clock/DST boundaries, transaction rollback and two-connection idempotency/locking tests. Record passed/failed/skipped/unrun outcomes and commands. No screenshots or zero-test runs count as foundation acceptance.

Stage-one exit criteria: empty isolated schema reproducibly migrates on the selected engine, auth/role boundaries work, core constraints and transaction primitives pass meaningful tests, compatibility blockers are resolved or explicitly bounded before claiming deployment fit, and instructions can be followed from the same checkout without a worktree. It does not yet demonstrate cattle/feed/report workflows. If host evidence is delayed, local foundation development can proceed on the proposed supported stack after review, with deployment compatibility clearly unconfirmed.

## Later staged checklist

### Stage two — animal identity, imports, lifecycle and mobs

- [ ] Permanent identity with either validated 16-character visual ID or 15-ASCII-digit RFID, leading zeros intact; uniqueness across all current/historical states, import duplicates and concurrent attempts.
- [ ] Minimum arrival import with map/preview/shared values/explicit selected-row atomicity; source PIC and NVD for purchases, nullable unknown price and missing breed/sex/mob/age completion flags.
- [ ] Purchase/birth/repurchase and age estimate/reference/DOB; birth $0 with mother's NLIS; no untagged temporary animals/pre-tag costs.
- [ ] Standard-user replace-tag workflow, reason/time/actor, historical lookups and permanent nonreuse; admin conflict resolution without identity merges.
- [ ] Zero/one mob, dated presence/membership, current moves and admin-only backdated correction preview.
- [ ] Sale/death field rules, exact group price split, restriction acceptance, membership/presence locks and same-identity repurchase retaining earlier revenue.
- [ ] Illness observation without an invented charge, so the acceptance scenario can record illness independently of treatment.

### Stage three — inventory and event-time allocations

- [ ] Feed receipts with package/kg/value calculations, introduced/home-grown details, matching-price/unit refills and distinct-price items; retire rather than destroy history.
- [ ] Feed only mobs using historical membership; fractional hay, grain total kg, milk kg/head and configurable supplements; equal exact cost allocation, historical price basis and all consumed/no wastage.
- [ ] Feed positive-start/one-cross-negative rule, zero/negative selection behaviour, serialised competition and inventory-only replenishment/stocktake with mandatory reason.
- [ ] Chemical batch/price/date-kind separation, compatible stock/dose units, exact sub-cent dose costs, no negative stock or automatic dose change, expired override/DOM distinction.
- [ ] Animal/whole-mob actual-dose treatment with historical members, combined restriction per animal, performer/submitting user separation and every section-2 record field.
- [ ] No chemical treatment drafts. Procedures with optional cost, group/per-head vet fees and castration sex history without product deduction.

### Stage four — corrections, permissions, recovery and concurrency

- [ ] Own eligible reversals before 24 hours from server submission; admin thereafter; all sale/death reversal admin-only at any age.
- [ ] Consequential change previews, stale preview refusal, immutable originals and compensating effects across stock, costs, participants and restrictions; no silent partial reversal.
- [ ] Backdated feed/treatment with event-time presence, stock chronology and current balance checks; no cost while off-property/dead.
- [ ] Browser-local pending recovery across reload, account isolation/logout behaviour, readable text download/share, review/retry/discard and honest storage limitations.
- [ ] Stable idempotency under lost response, two sessions and changed inputs; committed result returned once, uncommitted retry revalidation/material-change review.
- [ ] Real-engine overlap/race/deadlock/rollback tests, including membership changes competing with stock consumption.

### Stage five — reports, templates and LPA exports

- [ ] Allowlisted combined filters/columns/grouping/sort, current/as-of versus activity-time semantics, historical presence/mobs and full-lifetime P/L after selection.
- [ ] Lifetime AUD formula, active status/costs-to-date, unknown price/incomplete P/L, exact reconciliation and deterministic display rounding.
- [ ] Shared templates writable/deletable by any account, versioned/audited; no arbitrary SQL.
- [ ] PDF and XLSX exports for histories/P&L, mobs, inventories, feeding, treatments/restrictions, movements, audit and all six included LPA record sections.
- [ ] Full-field LPA export fixture, formula-injection protection, readable page/table layout, no inferred weights, photos, attachment UI, excluded sections or fabricated fields.

### Stage six — operations, backup, restore and deliberate retention

- [ ] Host-specific installation/WSGI/static/cron instructions validated in separately authorised staging; no deployment implicit in this document.
- [ ] Daily consistent self-contained archive, temporary-to-validated atomic publication, private immutable discovery/checksum and exactly three latest successful unique online versions.
- [ ] Future NAS Python pull script and Synology scheduler instructions, restricted transfer auth, temp download/hash verification/atomic publication, three local unique successful versions and failure-safe rotation. Do not connect to owner's NAS without separate authorisation.
- [ ] Controlled admin restore to an empty isolated installation, compatibility/environment/key preflight and explicit target confirmation; independently compare accounts/settings/templates/business/audit/stock/allocations.
- [ ] Default indefinite retention; only deliberate admin purge of currently off-property/dead animals ten calendar years after latest exit/death, repurchase resets; preserve nonreuse tombstones/shared totals and explain old backup copies.

### Stage seven — independent acceptance and handover

- [ ] Implement the unchanged companion event sequence with controllable simulated 2020 clock, local calendar-day offsets and fixed identity-to-fixture map. Do not bypass ordinary-user permission checks to generate the scenario.
- [ ] Two cohorts overlapping in calendar time, separately labelled stock items; run shared-item refill/concurrency branches too. Reset independent edge-case databases or reverse back to baseline without contaminating headline totals.
- [ ] Generate actual PDF/XLSX immediately after each cohort's sale; original-mob reports include deaths, survivor-only filters exclude them explicitly.
- [ ] Complete all 13 error/correction branches: identifiers, tags, reversal timing, feed boundaries, chemical shortage/expiry/units, historical mobs, connectivity, concurrency, exits/repurchase, missing data/birth, report filters/templates, inventory corrections/retirement, retention/restore.
- [ ] Verify critical phone/desktop browser paths against the chosen engine and actual exports, not mocks/screenshots alone. Use labelled synthetic data only; no real NLIS service calls.
- [ ] Record actual framework/engine versions, commands/counts/failures/unrun checks, report paths and independent reconciliations; update README/operations and deliver a reviewable PR when that later delivery scope is authorised. Preserve archive SHA/ref in handover.

## Business-rule traceability

All rows below are **planned**, not implemented. Intended code/test destinations identify what a later implementation must deliver, without implying files already exist.

| Source requirement group | Design location | Future service / required evidence | Stage |
|---|---|---|---|
| Auth, accounts and roles | ADR; DB account tables | `accounts`; first-admin/admin reset, shared financial access, role/CSRF tests | 1, 4 |
| Transactionality, decimals, time, property scope | DB types/transaction section | Shared domain primitives; direct SQL constraints, rollback, DST/order, exact residual and scope tests | 1–4 |
| Stable IDs, validation, tag replacement/nonreuse | DB identity tables | `animals`; manual/import/historical/cross-state duplicates, replacement/reversal lineage | 2, 4 |
| Birth, purchase, missing values and age | DB lifecycle/attributes | `animals`/`imports`; mother requirement, explicit zero versus unknown, age as-of tests | 2 |
| Mob/presence history and backdating | DB temporal rules | `mobs`; event-time membership, backdated admin preview and off-property/dead rejection | 2–4 |
| Sales/deaths/repurchase | DB lifecycle/financial rules | `animals.lifecycle`; destination/NVD exceptions, exact group sale, locks/revenue accumulation | 2–4 |
| Feed inventory/receipts/negative-stock rule | DB inventory transaction rules | `inventory`/`feeding`; fraction/unit/cost bases, crossing once, concurrent competitor, stocktake/refill | 3–4 |
| Chemicals, dose, restrictions, procedures/vet | DB activity/restriction tables; LPA section 2/6 | `activities`; 20 L conversion, no negative chemicals/dose advice, expiry override, fees/castration | 3–4 |
| Correction/undo eligibility and conflicts | DB reversal section | `corrections`; own 24-hour boundary, admin-only sale/death and stale/dependent-preview tests | 4 |
| Connected-only recovery and idempotency | ADR recovery; DB submissions | `recovery`; loss before/after commit, reload/account switching, retry/discard/concurrency browser tests | 4 |
| AUD lifetime finance/report semantics/templates | DB report section | `reports`; lifetime-selected IDs, death/current/as-of variants, incomplete price and template audit | 5 |
| All included LPA fields/overrides/exclusions | LPA matrix | Full-field synthetic export coverage and PDF/XLSX layout assertions | 3, 5 |
| Consistent three-version backup/NAS/restore | DB operations; runtime gates | `operations`; fail-before-publish, rotation/dedup/race/hash/isolated restore comparison | 6 |
| Deliberate ten-year retention/nonreuse | DB purge policy | `retention`; calendar boundary/latest exit/repurchase, shared-event reconciliation/tombstones | 6 |
| Future weights/multi-PIC/paddock occupancy | DB extension points | Future migrations only; no initial placeholder interfaces | Documented now, later features |
| Acceptance sequence, browser/report evidence | Original companion scenario | Real-engine suite, two cohort report pairs and all 13 branches with independent expectations | 7 |

## Independent acceptance anchors

Keep the companion document unchanged. Tests must load expected results independently of application calculations. Fixture dose/prices, bag sizes, dates and cohort scale are not business constants.

| Expected result | April | August | Combined |
|---|---:|---:|---:|
| Original animals / deaths / sales | 12 / 2 / 10 | 24 / 4 / 20 | 36 / 6 / 30 |
| Lifetime costs including deaths, AUD | 10,818 | 21,636 | 32,454 |
| Sale revenue, AUD | 20,000 | 40,000 | 60,000 |
| Lifetime P/L including deaths, AUD | 9,182 | 18,364 | 27,546 |
| Milk remaining, kg / AUD | 17.4 / 87 | 34.8 / 174 | 52.2 / 261 |
| Chemical remaining, mL / AUD | 50 / 25 | 0 / 0 | 50 / 25 |

April survivor-only P/L is $9,525, deaths -$343; grain and hay are exhausted; unused inventory is not animal expense. Final hay is day 411 and sale day 412. Preserve all original per-animal expectations and test variations from the supplied scenario. Preparation independently checked headline arithmetic only; none of the application acceptance tests or cohort reports has run.
