# StockLOG acceptance scenario

Status: proposed deterministic test fixture, 23 October 2026. Prices, precise dates, dose, bag size, death timing and scaling below are TEST ASSUMPTIONS, not additional business requirements or veterinary advice. Do not use these synthetic records on production services or the real NLIS system.

## Instructions for the rebuilding agent

Read this file before implementing tests. Implement repeatable integration tests on the production database engine and browser tests of critical workflows. Generate actual PDF and XLSX reports; inspect content, totals and readable layout. Deliver a test-results file identifying passed, failed and untested assertions and report paths. Never claim an unexecuted check passed. Keep fixtures isolated from production. Use a controllable test clock: historic events and submissions occur in simulated 2020; do not bypass permission checks to seed ordinary user workflows. Reset the database between independent edge-case tests.

## Fixed fixture assumptions

Timezone Australia/Melbourne; store Unix seconds. Admin A and standard users B and C. One synthetic property and syntactically valid synthetic source/destination PICs; required NVDs populated. All animals Angus, purchased at estimated age one week, $100/head. Generate unique 16-character visual IDs and unique 15-digit RFID strings, including a leading-zero case; persist a stable identity-to-animal fixture map. Start with no stock, animals or transactions.

Mob April: arrive 1 April 2020 09:00, 12 calves: A01–A08 male, A09–A12 female.
Mob August: arrive 1 August 2020 09:00, 24 calves: B01–B16 male, B17–B24 female.
Day 0 means arrival day; all offsets are local calendar days, not fixed 86400-second increments across daylight saving. Record arrivals before feeding on day 0.

| Commodity | Package | Unit price | Cost basis |
|---|---|---|---|
| Milk powder | 20 kg bag | $100 | $5/kg |
| Calf grain | 26 kg bag | $26 | $1/kg |
| Hay | 330 kg roll/bale | $65 | $65/bale |
| Synthetic treatment product | 100 mL bottle | $50 | $0.50/mL |

Procedure cost $10/head. Sale $2,000/head. No other costs. Treat with synthetic dose 2 mL/head daily for five days; 28-day restriction. These values test arithmetic only.

## April lifecycle

1. Import 12 animals with IDs, arrival, source PIC and NVD; review and confirm. Assign mob April. Purchase total $1,200.
2. Receive 12 milk bags: 240 kg, $1,200. Feed 0.350 kg/head at 08:00 and 17:00 daily from day 0 through day 67 inclusive, except day-0 first feed at 10:00. Replenish before any feed would exceed remaining stock, using whole 20 kg bags at the identical price; increase the same item and retain each receipt transaction. Never replenish after the final milk feed.
3. Day 7: record illness for A01–A05 without inventing a charge. Day 14–18 inclusive, 09:00: individually treat those five animals, 2 mL each/day. Receive one bottle before use. Each sick animal consumes 10 mL costing $5; total 50 mL/$25. Remaining chemical 50 mL/$25.
4. Day 18 at 18:00, after both milk feeds and the fifth treatment, A01 and A02 die. Record reason and $0 proceeds, no destination PIC or NVD. Mob has 10 active animals; future milk costs exclude deaths.
5. Day 28 09:00: castrate surviving males A03–A08, $10/head, no chemical deduction. Six procedure costs total $60. Record sex change/history; females unchanged.
6. Day 28 before feeding: receive 20 grain bags, 520 kg/$520. Feed 13 kg/day at 12:00, day 28–67 inclusive: exactly 40 feeds and 520 kg. Last stock balance zero; subsequent grain feed blocked. Stop all milk after day 67.
7. Day 68: receive 100 hay bales, 33,000 kg/$6,500. Feed two bales at 12:00 weekly on day 68 + 7k, k=0..49. Exactly 50 feeds exhaust hay; each survivor receives $650 total hay cost.
8. Day 412 at 12:00, one day after final hay feed: sell all 10 survivors at $2,000/head. Require identifiers, destination PIC, sale timestamp and NVD. End memberships and lock records. Produce mob lifetime P/L PDF and Excel, including the two deaths as original members, plus survivor-only filtered reports.

### April independent expected totals

Milk: first 19 days 12 × 0.7 kg/day = 159.6 kg; next 49 days 10 × 0.7 = 343 kg. Total 502.6 kg/$2,513. Receipts: 520 kg/$2,600 (26 bags); remainder 17.4 kg/$87.

Each deceased animal: milk 13.3 kg/$66.50 + purchase $100 + treatment $5 = $171.50 cost, $0 income, -$171.50 P/L.
Each survivor: milk 47.6 kg/$238 + purchase $100 + grain $52 + hay $650 = $1,040 base cost. A03–A05 add $5 treatment and $10 castration: $1,055 cost/$945 P/L each. A06–A08 add $10 castration: $1,050/$950 each. A09–A12: $1,040/$960 each.

Mob totals: purchases $1,200 + milk $2,513 + grain $520 + hay $6,500 + antibiotics $25 + procedures $60 = $10,818. Sales $20,000. Lifetime P/L including deaths $9,182. Survivor-only P/L $9,525; deaths -$343. Unconsumed inventory is not an animal expense.

## August lifecycle and overlap

Repeat using 24 calves (16 male, 8 female), 24 initial milk bags, 40 grain bags and 200 hay bales. Ten animals B01–B10 ill; treat all ten for five days. Four B01–B04 die after day-18 feeding/treatment. Castrate B05–B16 (12 males). Double grain rate to 26 kg/day and hay to four bales/week so stage durations match April. Milk remains 0.350 kg/head twice daily, not double per head. Use a separate test-labelled stock item per cohort at identical unit costs to independently reconcile consumption during overlap; separately test shared-item replenishment below.

August expected: 20 survivors; milk 1,005.2 kg/$5,026, receipts 1,040 kg/$5,200, remainder 34.8 kg/$174. Grain 1,040 kg/$1,040 consumed; hay 200 bales/$13,000 consumed; chemical 100 mL/$50 consumed; procedures $120; purchases $2,400. Total cost $21,636, sales $40,000, P/L including deaths $18,364. Sell on August day 412. Generate PDF and Excel immediately after sale.

Combined: 36 original animals, six deaths, 30 sales; costs $32,454; sale proceeds $60,000; P/L $27,546. Milk remainder 52.2 kg/$261; chemical remainder 50 mL/$25. Cohorts overlap in calendar time: no cross-mob allocation permitted.

## Error and correction branches

Run each branch independently or reverse it back to the baseline so headline totals remain unchanged.

1. Duplicate IDs: reject reused visual or RFID identifiers in manual entry, within one import and against active/exited/dead/historical-tag records. Reject incorrect lengths/non-numeric RFID. A conflict attaching an RFID to the wrong animal requires admin resolution; never silently merge.
2. Lost tag: standard user replaces A03 identifiers on day 35. Preserve internal animal identity, costs, restrictions and memberships; log old/new values and reason. Historical IDs cannot register a new animal. Reports include tag lineage; current identifier resolves the original animal. Undo/reversal must never release an old identifier for reuse.
3. Hay mistake: enter three bales instead of two, undo within 24 hours, enter two correctly. Net deduction two/$130; preserve original, reversal and corrected event. After 24 hours standard user denied; admin can correct with review. Test audit attribution and reconciliation.
4. Feed boundaries: starting 10 bales, feed 12: stock -2, allocate $780. Next feed blocked. Add 10: stock eight. At exactly zero block feeding. Fractional hay 0.5 bale deducts 165 kg/$32.50. No double charge on replenishment.
5. Chemical shortage: 8 mL available for five × 2 mL: reject atomically, no cost/deduction. User may edit quantity to accurately reflect an actual smaller dose; never auto-adjust or recommend dosage. No draft creation. Expired-product use requires logged override; manufacture date alone must not trigger expiry logic. Verify 20 L/$250 converts to $0.0125/mL.
6. Historical mob membership: move A03 to a new mob; enter a feeding dated before the move and one after. Allocate by event-time membership. Admin-backdated movement previews changes to existing feeding/treatments and applies audited adjustments, not destructive rewrites. Standard user cannot backdate movement.
7. Connectivity: server unreachable preserves readable pending input; reload browser, review/download text, retry or discard. Server commits but response is lost: retry same submission ID returns original result, no duplicate allocations. Revalidate after another user's changes. Discard local pending entry never reverses server data. Scope pending entries to signed-in account.
8. Concurrent stock consumption: two sessions consume same item; serialize availability checks and changes. Feed may cross zero once; competing request sees nonpositive balance and fails. Chemicals never negative. Full transaction succeeds or none of its allocations apply.
9. Exits: active restriction warning requires logged acceptance but permits sale. Standard user cannot reverse sale/death at any age; admin can reverse with audit. Repurchase reopens same animal, accumulates purchase cost, preserves sale income; no new duplicate animal.
10. Missing data: import missing price/breed/sex/mob with visible missing-data review. Unknown purchase price makes P/L incomplete, never $0; explicit farm-born $0 is complete. Unassigned animals receive no mob events. Farm-born entry requires mother's NLIS; no temporary animals.
11. Reports: combine breed/sex/age/current-status filters; historical presence uses occupancy intervals. Animals selected by a date filter still show full lifetime P/L. Estimated weeks advance from reference date. Save a template, another user modifies/deletes it with audit. Verify PDF and XLSX rows/totals against independent calculations, including deaths and retired inventory history.
12. Inventory: stocktake reason required; adjustment does not rewrite earlier animal costs. Same-price/unit/batch matching refill increases stock and preserves receipt history; different prices or chemical batches stay separate. Retiring item hides it but reports retain links.
13. Retention and recovery: reject deletion of active animals and animals less than ten years since latest exit/death, including repurchased animals. Admin deliberately purges only eligible data, preserving unrelated ledgers and historical-ID nonreuse protection. Back up then restore to an empty isolated deployment; verify users, settings, templates, identifiers, balances, costs and audit history.

## Completion evidence

Include repeatable commands, framework/database versions, scenario fixtures, independent expected-result checks, failed assertions, critical mobile/desktop browser evidence, and two cohort PDF/XLSX report pairs. Verify sale/membership locks, financial completeness and exact allocation reconciliation. Do not treat generated screenshots or reports alone as proof of database correctness.
