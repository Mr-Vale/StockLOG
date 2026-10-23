# StockLOG complete replacement — implementation agent prompt

## Assignment

Rebuild https://github.com/Mr-Vale/StockLOG as a complete, deployable cattle-management web application. This specification is authoritative over the old code and its summary. Start with an empty production database; no legacy-data migration. Read the existing repository and applicable AGENTS.md instructions first. Before replacing old files, preserve the current commit in a clearly named archive branch/tag and document its SHA. Do not rewrite history or destroy the archive. Work on a rebuild branch and deliver a reviewable pull request unless repository instructions require another workflow. No production deployment or live database changes are authorised by this prompt.

Place all new source, database migrations, dependency locks, configuration examples, cPanel entry points, installation instructions, tests, backup/restore tools and NAS pull script in this repository. Never commit live databases, credentials, secrets or real personal data. Use the existing implementation as workflow reference, not an architecture constraint.

Read `StockLOG_acceptance_scenario.md`, place it in `docs/testing/`, and use it as the independent acceptance fixture. This prompt and scenario are companion files: request the scenario if absent rather than inventing its contents. Preserve labelled fixture assumptions; do not confuse them with requirements. Produce the implemented requirements and operational documentation in the repository.

## Architecture and deployment

Build one responsive browser application for phones and computers; no native app installation. Phone workflows prioritise quick entry and enquiries; desktop supports detailed administration, imports and report building. Browsers communicate with an authenticated backend, never directly with SQL.

Use a Python-first backend and MariaDB/MySQL with transactional storage in production. Python 3.9 is the runtime currently reported available by the owner; verify actual hosting versions, maintained framework compatibility, database driver, WSGI/application mechanism, cron, SSH/SFTP and export capabilities. Do not silently pin obsolete dependencies merely to meet 3.9 or claim a modern framework supports it without checking. Document a runtime upgrade prerequisite if no maintained combination is available. Keep host-specific choices isolated. cPanel shared hosting is the intended target, possibly HostGator initially and Skyrack later. Do not require Docker, root access, persistent background workers or a Node server on the host. Local development tooling may differ, but prove deployment dependencies fit the target. Choose a simple maintainable stack after capability inspection and record the decision and limitations. No paid hosting purchase is authorised.

Use transactional business services, migrations and explicit constraints. Keep stock changes, per-animal allocations, event effects and audit records atomic. Serialize competing inventory mutations. Use fixed-precision decimal arithmetic, never binary floats for quantities/money. Preserve allocation totals exactly and retain sub-cent precision for dose costs; document deterministic display rounding. Prefer a transaction/event ledger with stable internal animal identity and historical associations; full event sourcing is not mandated. Record event/effective time separately from submitted/recorded time. Timestamps use Unix seconds; user settings control display format and timezone. Handle daylight saving and same-day event order.

Initially one PIC and 1–10 accounts. Include property scoping in the schema for future multi-PIC switching, without building that interface now. Use HTTPS, hashed passwords, safe sessions, server-side authorisation, CSRF protection where applicable, validated imports and parameterised queries. Report filters must use allowed fields/operators, not executable user SQL.

## Accounts and permissions

Two roles: administrator and standard user. At least one admin; safe first-admin setup, no public registration. Admin creates accounts and resets passwords. All users may read all data and financials; run any report; add/adjust inventory; register purchases, sales and deaths; feed/treat; manage current mobs; and replace ear tags. Any user may create/change/delete shared report templates; log these actions.

Users can reverse their own eligible actions within a rolling 24 hours from submission. After that admin is required. Sales and deaths can only be reversed by admin, regardless of elapsed time. Only admin through desktop administration may backdate mob movements. Admin resolves identifier conflicts and deliberately purges eligible old data. Preserve original records with logged reversals/corrections and before/after effects. Preview consequential changes; refuse silent partial reversals when later events conflict. Define desktop administration as an authorised workflow, not security based on screen size.

## Animal identity and registration

Stable internal animal key independent of replaceable tags. NLIS visual ID: exactly 16 characters. RFID: exactly 15 ASCII digits. Both stored as strings, preserving zeros, and interchangeable for lookup. Require either at registration, permit adding the other later. Server/database enforce uniqueness across active, exited, dead and historical identifier assignments, including duplicates within one import. Conflicting links block and require admin resolution; never silently merge animals.

Dedicated Replace ear tag form available to standard users: identify existing animal, record new NLIS and/or RFID, effective time, reason, responsible user; preserve prior identifiers permanently and prevent reuse for other animals. Preserve animal history, finances and restrictions. Historical identifiers must remain traceable to their owner, with clear current/retired status. An undo must not release a retired identifier for another animal. If permitted retention deletion removes animal detail, retain the minimum identifier reservation needed to honour permanent nonreuse; document this distinction.

Animals do not exist in StockLOG before tagging; no temporary newborn IDs or pre-tag costs. Entry source is purchase or birth. Fields: entry timestamp, purchase cost, breed, sex, estimated age in weeks at entry or known DOB; optional source name/address. Farm-born entry costs $0 and requires mother's NLIS. Store age estimate and its reference date so estimated age advances; label estimation. Purchased-arrival imports require each animal's NLIS or RFID, arrival date, source PIC and NVD. Normal users may record earlier arrivals.

CSV and spreadsheet imports: map columns, preview missing data and validation errors, detect duplicates, optionally apply shared values, then confirm valid submissions with clear atomicity rules. Breed, sex, purchase cost and mob can be missing, filled later. Missing purchase price is unknown, never implicit zero; mark P/L incomplete. An unassigned animal receives no mob feeding/treatment. Avoid invented age values; flag missing required age for completion if absent from a minimum import.

Animals occupy zero or one mob at a time, retaining dated membership intervals. Create mobs and move individuals, selections or entire mobs. No ordinary backdated movements. Normal users can backdate feeding/treatments; resolve eligible animals from historical event-time presence/membership, not current headcount. Block invalid events while animals were off-property or dead. Admin historical movement corrections preview affected allocations/restrictions and preserve corrective history.

Sales require each identifier, destination PIC, exit timestamp, price and NVD. Accept per-head prices or group total split equally. End memberships and lock exited animals against ordinary changes/cost accumulation; repurchase reopens the same animal, adds purchase cost and retains earlier sale revenue. Death requires identifier, timestamp, reason, $0 proceeds, no destination/NVD. Lock against further accumulation unless admin corrects death. Admin corrections and reversals are explicit audited exceptions to locks.

## Feed inventory and transactions

Inventory fields: product, feed type, total unit count, kg/unit, price/unit, total kg, total value. Derive calculated values server-side. Include introduced-feed supplier/source, delivery date, declaration details and storage location. Matching price/unit specifications can replenish the same item, with distinct receipt history; new prices or unit sizes become separate selectable items. Home-grown feed uses same receipt process and requires a value. No wastage allocation: all recorded feeding is treated as consumed.

Consumption: hay in fractional bales, converted using selected item kg/bale; grain in kg; milk powder in kg/head multiplied by event-time headcount; other feed/supplements configurable units or total kg. Do not force every feed to use a per-head dose. Feed only a mob; use a one-animal mob if needed. Allocate transaction cost equally to members at effective time, preserve participant list, quantity and historical cost basis. Later refills/prices never silently reprice old consumption.

Feed may be deducted only if its starting balance is positive. A single accepted event may cross into negative: 10 bales minus 12 becomes -2; charge all 12. No further feed from nonpositive stock until replenishment/correction makes it positive. Serialize simultaneous submissions to preserve this rule. Replenishing -2 with 10 leaves 8; no second animal charge for replenishment.

Stocktake accepts actual remaining balance and requires reason; record an inventory adjustment, not retrospective animal repricing. Zero-stock items hidden from feeding selection but retained for refills; negative items visible for correction and unavailable to feed. User removal retires inventory, preserving historical associations.

## Chemicals, treatment and procedures

Inventory: entry date, product, container count, quantity/container, stock unit, dose unit, expiry or DOM with explicit date type, batch, combined withholding/ESI days, purchase price/container, cost/stock unit, cost/dose unit, remaining quantity/value. Separate batches, dates and prices. Convert compatible units reliably: 20 L costing $250 means $12.50/L and $0.0125/mL.

Treat one animal or entire historical mob; mob dose identical per animal. Exclusions require moving animals before treatment. User selects product then actual dose/head; no weight dosing calculations in initial release. Required stock = dose × headcount. Chemicals cannot go negative. Warn/reject insufficient submissions atomically; user may edit actual dose or correct stock, but system never reduces/recommends dose. No treatment drafts.

Expired product warning can be explicitly overridden, logged. DOM alone is not expiry. Administered-by defaults to user and may name a different administrator of the treatment (vet/contractor etc.); retain actual submitting user separately. One combined withholding/ESI days field; calculate per-animal restriction end and latest applicable restriction across treatments. Warn on departure during restriction, require logged explicit acceptance but permit departure. Preserve restriction history through mob/tag changes.

Procedures can omit chemical, with optional cost/head. Vet fees apply to one animal or whole mob, by per-head charge or group total allocation. Include vet/procedure costs in animal P/L without chemical deduction. Castration is a dated procedure which also changes sex and preserves previous state.

Map all fields of included livestock-treatment template section, including adverse reactions/broken-needle and other relevant record details, not only cost fields. These records remain data fields, not attachments.

## Finance and reports

AUD lifetime P/L per permanent animal identity = all sale revenue minus all purchase costs, allocated feed, chemicals, procedures and vet fees. Farm-born $0 is complete; missing purchase cost marks incomplete. Multiple sale/repurchase cycles accumulate in one history. Do not report active animals as having a final realised sale outcome; show costs/revenue to date and current status. No predictive values. Exclude transport, agent fees, levies and unrelated fees.

Report builder: selectable data/columns, combined filters, grouping, sorting, historical presence intervals, and PDF/XLSX downloads. Include individual lifetime histories/P&L, mobs, inventory, feed, treatments, restrictions, arrivals/exits, required LPA records and audit. Filters can combine breed, sex, age, mob, animal, property status and dates as relevant. Explicitly distinguish current/as-of attributes from activity-date selection. Select animals using report filters, then always show each selected animal's full financial lifetime; never clip P/L transactions to the date filter. Historical mobs include appropriate former members. Estimated age calculations reference selected as-of date. Clearly show missing financial data and filter meanings on exports.

Named report templates shared; any user may edit/delete, audited. Prevent spreadsheet formula injection in exported text. Reports reconcile to stored allocations, preserving exact totals and readable layout.

## Browser submission recovery

Server-connected operation; no full offline farm database. On unreachable server or uncertain confirmation, clearly show not confirmed, retain pending input locally across browser reload, offer readable plain-text download/share plus review/retry/discard. No email sending required. Ordinary draft-saving interface is not required. Protect pending entries from cross-account access on shared devices.

Each submission carries stable idempotency identity. If server committed before response disappeared, retry returns original outcome, never duplicates. On genuine retry revalidate historical membership, stock and permissions; show material changes for review. Local discard never reverses a committed server event. Explain browser-local storage limitations honestly; do not promise recovery after users clear browser data.

## LPA scope and source handling

Source template is `may23-lpa-farm-records.xlsx`, supplied separately. Included sections: 2, 3C, 3D, 5A, 5B, 6. Exclude 1/1A/1B, 3A/3B, 4, 7A/7B/7C, 8 and stray contents label `ter`. No document/photo upload feature; CSV/XLSX structured-data imports and controlled restore archives are exceptions, not attachment storage.

Inspect included sheets and create a field-to-screen/database/report matrix covering every relevant field, identifying explicit owner overrides: combined withholding/ESI field, no initial weights, section 4 excluded. Do not invent unseen template contents; if workbook absent, mark mapping unverified and ask for source while progressing other implementation. Do not claim regulatory compliance solely from template mapping.

## Backups, restore and retention

Server cron generates daily self-contained StockLOG restore archive. Keep exactly three latest successful versions online. Generate to temporary filename, validate, atomically publish and only then rotate oldest; failures retain prior good files. Provide stable authenticated discovery of latest completed archive, immutable identity/checksum and safe transfer so a NAS pull never reads a changing slot mid-download. No publicly accessible backup URL or embedded credentials.

NAS runs a Python pull script daily via Synology Task Scheduler, authenticates by supported SSH/SFTP or restricted authenticated transfer, downloads latest to temporary local path, verifies completion/checksum, then publishes. Keep three latest successful unique backups locally; retries do not create duplicate versions; failed downloads do not delete good copies. Log failures and document schedule/timezone, authentication setup and recovery. Do not automate browser login to cPanel as the default backup mechanism.

Archive includes consistent database export, all business/audit records, accounts/password hashes, settings, report templates, application/schema version manifest, checksums and necessary restore configuration. Include versioned application release material or exact reproducible dependency/source reference; document environment-specific values and encryption keys which require protected handling. Never publish backup secrets in Git. Use supported transactional DB export or controlled snapshot, not a raw copy of live MariaDB files. Encryption/key custody and access controls must allow owner recovery without sacrificing secret protection.

Fresh install supports admin-only restore through a documented supported interface or maintenance command: validate checksum/archive paths/schema compatibility, preflight, handle target confirmation, restore consistently and provide clear failure/recovery behaviour. Map old installation settings to new server credentials/paths safely. Document compatible restore versions and migrations; do not promise arbitrary future-version compatibility. Demonstrate restoring a generated backup into an empty isolated server installation and compare records, accounts, balances, allocations, audit and templates.

Default indefinite retention. No automatic age purge. Admin deliberate deletion only if animal currently off-property and at least ten calendar years since most recent exit/death; repurchase resets eligibility. Preview affected data, require confirmation, log deletion and preserve unrelated animals/shared transaction totals. Resolve shared-event retention and identifier reservation explicitly. Explain that rotated historic backup copies may retain deleted records until rotation. Never purge merely because a transaction itself is ten years old.

## Future schema provisions, no initial user features

Provide documented extension points/migrations or suitable tables for dated weights per internal animal identity, future weight gain versus feed cost reports; multiple properties/PIC switching; paddock geometry/map and historical occupancy traceable to animals, multiple mobs sharing a paddock. No weight/map/paddock management interface in initial delivery. Avoid scattering dummy placeholder UI across the application.

## Delivery stages and acceptance

1. Inspect/archive legacy, verify host constraints, record architecture and field mapping, establish schema/migrations/auth.
2. Animal/import/tag replacement, lifecycle, mobs and historical membership.
3. Feed/chemical receipts, stocktake, feeding and treatment/procedure allocations.
4. Corrections/permissions, pending submission recovery and concurrency/idempotency.
5. Reports/templates, PDF/XLSX generation and required record coverage.
6. cPanel setup, daily server backup, NAS pull, fresh-install restore, retention tools.
7. Run complete companion scenario against production database engine; verify critical phone/desktop browser workflows. Update README and operational handover.

Keep implementation modular and understandable, with a service layer for business transactions. Do not stop after a UI mockup or schema. Add meaningful tests for calculations, permissions, history, concurrency, failure recovery and backup restoration. Follow companion fixture event sequence and independent expected totals. Test cohort overlap, not just two isolated repeated scenarios. Produce PDF/XLSX after each sale and independently reconcile animal and mob totals including deaths; fixture prices and doses are synthetic arithmetic inputs only.

Deliver a requirements traceability checklist with links to code/tests, actual test output and commands, generated report examples, deployment and restore instructions, archive SHA and reviewable change summary. Identify blocked host checks, missing sources and unexecuted tests honestly. Do not mark a requirement complete based only on a screenshot, mocked service or generated report. Keep owner-facing UI simple and free of internal implementation jargon.
