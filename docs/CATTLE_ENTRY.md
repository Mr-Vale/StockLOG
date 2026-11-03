# Cattle Entry and Active Cattle

The homepage and authenticated layout preserve the existing logo, palette and system font. The title bar identifies the selected property/PIC. A collapsible sidebar contains Active Cattle, Inventory, Reports, History, Import, Settings and administrator-only Administration. Administration contains property/PIC creation and access management, including the first-property setup route. Activity/data links precede charts.

Selection changes are session-local until Save selection updates the account's existing default pair. Saving collapses the card; restoring a valid account default starts compact. Change selection expands it. The existing signed context generation and server transition deadline remain authoritative; the pause is five seconds. Reduced-motion users retain a stationary indicator and readable destination. Timer tests advance the browser clock and separately control the server deadline.

## Date-only conversion

Purchase, Birth and Re-Purchase use ISO calendar dates as input, defaulting to the selected property's current date. The service converts each `entry_date` to **00:00:00 in the selected property's IANA timezone**, using the existing validated `clock.local_timestamp` conversion, then stores Unix seconds in presence, age reference and entry event metadata. The enclosing batch event uses the earliest date. Calendar days crossing DST therefore need not be exactly 86,400 seconds apart. Converting the timestamp back in the same property timezone preserves the chosen calendar date. An exceptional timezone/date with nonexistent or ambiguous midnight is rejected by the existing conversion validation rather than silently shifted.

New form entries require an administrator for dates before the property-local current date, reject future dates and reject DOB after arrival. Existing timestamp-based imports and unrelated workflows retain their timestamp conventions and permissions. The older rebuild specification allowed ordinary users to enter earlier arrivals; the current request's administrator-only historical date rule is applied to the new date-only forms. DOB remains unknown if omitted from Birth. Review dates follow the account's supported date format with its time suffix removed, using the property timezone so a date-only event never shifts a day with the viewer's timezone. Active Cattle explicitly uses DD/MM/YYYY.

## Temporary review and final save

The browser carries signed, account-bound input with a stable submission key and signed property/PIC generation. There are no permanent draft records. Add to list runs a rolled-back transaction preview of the whole candidate batch, so duplicates across staged rows are checked before any animal is confirmed. Modes retain the list; Edit replaces an explicit row and Remove deletes only that row. Shared event/source/mob details may carry forward; animal identifiers and mother identification reset. Review shows acquisition cost as unknown when omitted.

Save animals validates the complete signed input again, rechecks current forms/permissions, and invokes one atomic `services.execute(register)` transaction. The property lock serialises competing entries; permanent global identifier uniqueness prevents concurrent creation from another property. Identifier lookups cover current and retired tags. A rejected row rolls back all animals, periods, allocations, events, submission and audit changes. The signed input remains available with the affected row number. Retrying identical confirmed input returns the original submission result. A changed property/PIC generation cannot redirect a list: it is displayed for review, saving is blocked, and the user must explicitly restart it. Lists expire after 24 hours; no persistence beyond temporary browser input is promised.

Birth's source PIC/name/address and confirmed zero cost are derived by the service. Optional mother identification accepts either identifier format and records its kind in event metadata. Purchase cost omission and every new Re-Purchase cost omission create an unknown purchase allocation. The new Re-Purchase form intentionally has no cost input, so administrators can complete that cycle's cost later through existing correction tools.

## Lifecycle resolution

**Re-Purchase only reopens the same permanent animal on its recorded PIC, after a valid previous sale/exit and after its latest presence has ended.** It preserves descriptive details, current and historical tags, treatments, all financial allocations and previous presence cycles. Historical tags may identify an animal but do not reactivate or replace its current tags. When both identifiers are supplied, each must already belong to that same animal; new/replacement tags use existing identifier tools.

The prior same-property cross-PIC repurchase behavior is explicitly removed. Neither Purchase nor Birth can reuse a permanent identifier, including one belonging to an exited animal. Another PIC's active animal must first exit; exiting still does not make a new identity or cross-PIC Re-Purchase valid. There is no automatic transfer and no new supported cross-PIC entry workflow in this change. Such movement requires administrator review and a separately specified workflow. Validation does not disclose the other property's identity or data.

Bulk Import remains **Purchase only**, with its existing mapping, review, permission and validation workflow. It shares `register` and therefore cannot bypass global tag reservations, lifecycle or PIC occupancy checks.

## Active enquiry calculations

Only active, non-purged animals on the selected PIC appear. Search accepts current or historical tags. All nine headings toggle sorting; missing values sort last in either direction. Identifier/mob/description sorts are case-insensitive text, sex sorts its displayed code, date sorts use calendar dates, value sorts use Decimal totals, and age sorts use elapsed days from the calculated birth/reference date.

Farm Entry Date is the current open presence start. Total Value is the reconciled lifetime sum of all non-sale allocation categories, including corrections and every acquisition cycle. Unknown unresolved purchase allocations produce an incomplete indicator. Sale proceeds are excluded. Age uses DOB, else estimated weeks at their reference date, else the current presence start; month anniversaries clamp to valid month-end dates. The display is remaining months-completed years, with a tooltip distinguishing estimated age and elapsed farm residence. Safe Sale Date is the later of the property-local current date and the maximum non-reversed, non-superseded applicable restriction date. A later shorter restriction cannot shorten it.

No model migration, installer modification, merge, deployment or production-data operation is part of this change. The installer Caddy ownership/mode fix and service-user validation remain intact.
