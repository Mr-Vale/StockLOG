# LPA source mapping: May 2023 workbook

Verified source: [may23-lpa-farm-records.xlsx](../reference/may23-lpa-farm-records.xlsx), SHA-256 `7354987c6a2423d59472ae8d6e93529d5c3d5ee4ab50b789b465ecf0a18178ba`.

All 18 sheets were traversed, including hidden `DATA`, formulas, merged cell regions, data validation, and DrawingML text. Raster images were inspected: navigation arrows and the excluded example property map; no additional included form fields were found there. All XML/relationship/VML/SVG parts parsed successfully. A second openpyxl read independently matched every sheet's nonempty-cell count; the workbook was never saved/reserialised, because openpyxl warns it cannot retain every Excel validation extension. Original bytes are preserved. Full sample rows are reference examples, not production data or requirements. See [inventory](evidence/workbook-inventory.json).

Included record sections are **2, 3C, 3D, 5A, 5B, 6** only. “Mapped” means a proposed screen, field and export route exists in this document, not that code or regulatory compliance has been delivered. Repeated blank form blocks map to the same fields. Dot-only print-boundary cells and “EXAMPLE RECORDS” watermarks are not business data.

Column names below refer to the proposed entities in [database design](database-design.md). Historical snapshots preserve what was known/recorded at the event, rather than substituting today's tags, mob, product, person or price. Report names are planned PDF/XLSX exports through the allowlisted report builder.

## Section 2: livestock treatment record

Use the first form block (rows 4–7); the remaining 34 repeated blocks add no distinct fields.

| Source cell and label | Proposed screen/input | Database field or derivation | Report field / explicit disposition |
|---|---|---|---|
| A4 Treatment date | Treat animal/mob: effective date/time | `business_event.effective_at`, property timezone snapshot | LPA treatment date/time; recorded/submitted time available separately |
| B4 Livestock description & location | Treatment description and location text | `treatment_event.livestock_description`, `.location_text` | Description/location as recorded; no paddock-management UI |
| C4 Tag number or mob/herd number | Animal identifier lookup or whole-mob selection | `event_participant.identity`, tag and mob snapshots | Event-time tag(s), mob and tag lineage, not only current IDs |
| D4 Number of livestock | Preview computed participant count | `business_event.participant_count`, participant rows | Exact historical count; no editable count overriding membership |
| E4 Product trade name | Chemical product/item selection | Item reference plus `treatment_event.product_name_snapshot` | Product as administered |
| F4 Batch number | Selected batch shown in preview | Receipt/item batch and `treatment_event.batch_snapshot` | Administered batch |
| G4 Product expiration date | Actual expiry, or explicitly DOM/unknown | Item `date_kind/date_value`, expiry snapshot | True expiry only in expiry column; DOM labelled separately; expired override included |
| H4 Dose rate/dipping or jetting rate (mL/L) | Actual dose/head and compatible unit; optional method/rate description | `treatment_event.actual_dose_per_head`, `.dose_unit`, `.administration_method`, `.rate_description` | Actual recorded dose/unit/method; no weight-dose calculator or recommended dose |
| H4 “& approx. live weight” | No initial weight input | Future `animal_weight` extension only | **Owner override: no initial weights.** Export marks “not collected in initial scope”, never invented weight |
| I4, example I5/J5 Treated by, name and contact number | Defaults to current user; may name vet/contractor with contact | `treatment_event.administered_by_name`, `.administered_by_contact`; separate `business_event.submitted_by` FK | Performing name/contact and separate submitting account |
| A6 Withholding period (days) | One combined withholding/ESI field | `treatment_event.combined_restriction_days` | **Owner override:** one combined value; if workbook-shaped output shows both headings, repeat same value labelled “combined”, not independent source values |
| B6 Export Slaughter Interval (days) | Same combined input | Same field as A6 | Combined policy made explicit; no second hidden ESI setting |
| C6 Date safe for slaughter | Derived per animal plus latest active restriction | `restriction.ends_at`, rule version/timezone; maximum across applicable treatments | Treatment safe-at date and animal's latest restriction; warnings and accepted departure override |
| D6 Adverse reactions | Treatment-wide text and optional per-animal detail | `treatment_event.adverse_reactions`, `treatment_animal_detail.adverse_reactions` | Reaction description, animal(s), “none reported” versus unknown distinguished |
| F6 Broken needle still in animal? | Yes/no/unknown plus affected animals and details | `treatment_event.broken_needle_status`, `.broken_needle_details`; per-animal overrides | Status/details tied to affected animals; not a document attachment |
| G6 Equipment cleaned/calibrated? | Yes/no/unknown, equipment text | `treatment_event.equipment_cleaned_calibrated`, `.equipment_description` | Recorded status and equipment; no fabricated positive default |
| H7 unlabelled date, formula `A5` in example | Optional cleaning/calibration date, default treatment date with confirmation | `treatment_event.equipment_checked_on` | Date retained explicitly; label is inferred from adjacent equipment fields and source formula, not presented as an unseen source heading |
| I6, example I7/J7 Equipment cleaned/calibrated by, name/contact | Responsible person's name/contact | `treatment_event.equipment_checked_by_name`, `.equipment_checked_by_contact` | Name/contact distinct from administering/submitting users |
| A2 record details within 48 hours | Show effective versus recorded time and late-entry flag | Derived `recorded_at - effective_at`, without changing permission rules | Timeliness column/warning; advisory source note, not a new 48-hour entry prohibition |

Procedures without chemicals and vet fees are supported by the business specification, not inferred from the workbook. They may share activity/history reporting but never manufacture product/batch/expiry values or chemical stock deductions.

## Section 3C: livestock feeding record

| Source cell and label | Proposed screen/input | Database field or derivation | Report field |
|---|---|---|---|
| A4 Feedstuff description | Feed selected item; product description | `inventory_item.product_name`, `feed_event.product_description_snapshot` | Historical feedstuff description |
| B4 Storage location | Receipt/item storage shown; actual location if different | `inventory_receipt.storage_location`, `feed_event.storage_location_snapshot` | Storage used for the feeding record |
| C4 Mob(s) fed | One mob per consumption event | `feed_event.mob_id`, event-time mob snapshot and participants | Mob name/ID; period report may list multiple events/mobs without reallocating costs |
| D4/D5 Feeding period, Start | Effective feeding timestamp | `business_event.effective_at` | Individual event start; aggregate start is earliest selected feeding |
| E5 Finish | Effective feeding timestamp for a point event | Same event timestamp; no invented multi-day consumption | Individual start=finish; aggregate end is last event with listed underlying events and gap semantics |
| F4 Person responsible for activity | Defaults to user, editable performing person's name | `business_event.responsible_name`, separate submitting account | Responsible name and submitting user |

A period report groups already recorded discrete feedings; it never spreads one cost over assumed animals/days. Grain/total kg, fractional hay, milk kg/head and configurable supplement units remain the business specification's distinct inputs.

## Section 3D: introduced stock feed

| Source cell and label | Proposed screen/input | Database field or derivation | Report field |
|---|---|---|---|
| A4 Date received | Feed receipt effective date/time | `inventory_receipt.effective_at` | Delivery/receipt date |
| B4 Feedstuff | Product/feed type description | `inventory_item.product_name`, receipt snapshot | Feedstuff name/type |
| C4 Amount | Package quantity, unit and kg/unit (compatible other units supported) | `inventory_receipt.package_count`, `.package_size`, `.stock_unit`, derived total kg where applicable | Original amount/unit and converted amount; avoid falsely converting volume to mass without a valid factor |
| D4 Origin of feedstuff | Supplier/source and origin | `inventory_receipt.supplier_name`, `.origin_text` | Source/supplier and origin; home-grown explicitly labelled |
| E4 CVD* or equivalent reference no. | Declaration type/reference/details | `inventory_receipt.declaration_type`, `.declaration_reference`, `.declaration_details` | CVD/equivalent details as structured text, no attachment upload |
| F4 Residue Analysis Certificate available / product tested (yes/no) | Separate yes/no/unknown certificate-available and product-tested fields, optional test reference/details | `inventory_receipt.residue_certificate_available`, `.product_tested`, `.residue_test_reference`, `.residue_test_details` | Both answers explicitly labelled; distinguish unknown, not a fabricated certificate |
| G4 Storage location | Receipt location text | `inventory_receipt.storage_location` | Receipt storage location |
| H4 Signed | Responsible declarant's typed name and confirmation | `inventory_receipt.signed_by_name`, `.confirmed_at`, submitting account | Typed signer, confirmation time and submitting account; not a claim of a cryptographic signature |

The source's feed-ban/fit-for-purpose guidance at A2 is explanatory text. Mapping does not certify feed safety, interpret laboratory evidence or automatically declare compliance. Home-grown receipts use the same inventory path and require a value as specified by the owner.

## Section 5A: bringing livestock onto the property

| Source cell and label | Proposed screen/input | Database field or derivation | Report field |
|---|---|---|---|
| A4 Date | Arrival/import effective date/time | `arrival.effective_at`, presence start | Arrival date/time |
| B4 NVD Serial No. | Required for purchased arrivals/imports | `arrival.nvd_reference` | NVD reference, string preserving zeros |
| C4 NLIS Upload ID | Optional external movement reference | `arrival.nlis_upload_reference` | Reference as entered; no automatic NLIS submission or claim it was completed |
| D4 No. of stock | Validated selected animals | `arrival_animal` count | Confirmed arrival count, reconciles to identifiers |
| E4 Destination paddock | Optional arrival-location/paddock text | `arrival.destination_paddock_text` | Recorded destination paddock; no map or paddock interface |
| F4 Breed | Per animal or shared import value; may be incomplete | Animal attribute and arrival participant snapshot | Arrival breed snapshot; unknown explicitly shown |
| G4 Sex | Per animal or shared import value; may be incomplete | Animal attribute and arrival participant snapshot | Arrival sex, distinct from as-of sex after castration |
| H4 Vendor name | Optional source name | `arrival.vendor_name` | Vendor name |
| I4 Vendor address | Optional source address | `arrival.vendor_address` | Vendor address |
| J4 Vendor PIC | Required for purchased arrivals/imports | `arrival.source_pic` | Source PIC, string |
| K4 Notes | Arrival/import notes | `arrival.notes` | Arrival notes |

Additional owner fields: stable animal identity, either validated tag, purchase cost/unknown flag, birth/mother reference and age estimate/reference or known DOB. Capture these separately; never substitute guessed ages or zero prices. Source notes about NLIS responsibilities are not an authorisation to integrate with the real NLIS system. Farm-born entry is a distinct path, not a fictitious purchase from a vendor PIC.

## Section 5B: moving livestock off the property

| Source cell and label | Proposed screen/input | Database field or derivation | Report field |
|---|---|---|---|
| A4 Date | Sale effective date/time | `departure.effective_at`, presence/membership end | Exit time |
| B4 NVD Serial No. | Required for sale | `departure.nvd_reference` | String NVD reference |
| C4 NLIS upload ID | Optional external movement reference | `departure.nlis_upload_reference` | Recorded reference; no claimed external upload |
| D4 No. of stock | Confirm selected identifiers | `departure_animal` count | Sale count and per-animal identity |
| E4 Paddock of origin | Optional exit-location/paddock text | `departure.origin_paddock_text` | Origin as recorded, not current mob guessed as a paddock |
| F4 Breed | Snapshot from each animal at exit | Exit participant snapshot | Exit breed; grouped rows split/display mixed descriptions honestly |
| G4 Sex | Snapshot from effective-time history | Exit participant snapshot | Exit sex, including procedure history |
| H4 Destination | Destination PIC required plus destination description | `departure.destination_pic`, `.destination_name` | Destination name/PIC, without dropping the owner's required PIC |

Additional owner fields: per-head/group sale price and allocation, active restriction warnings and explicit acceptance. Deaths are separate lifecycle records with timestamp/reason and $0 proceeds: destination/NVD not required; label deaths separately from sales in lifetime/movement reports. Section 4 transport preparation is excluded, so no fit-to-load/yarding checklist is introduced through this matrix.

## Section 6: chemical inventory

| Source cell and label | Proposed screen/input | Database field or derivation | Report field |
|---|---|---|---|
| A4 and drawing checkbox labels: Veterinary only / Agricultural only / Combined | Item category and report category filter | `inventory_item.chemical_category` (`veterinary`/`agricultural`), report filter | Veterinary/agricultural/combined report heading; agricultural inventory does not imply crop/paddock-treatment features |
| A6 Date received | Chemical receipt date/time | `inventory_receipt.effective_at` | Receipt date |
| B6 Product name | Chemical product selection/name | `inventory_item.product_name`, receipt snapshot | Product name |
| C6 Quantity | Containers × quantity/container with stock unit | Receipt count/size/unit, calculated received total | Quantity received with unit; remaining balance/value separately, no conflation |
| D6 Expiry date or date of manufacture | Date plus explicit date kind | `inventory_receipt.date_value` | Date as entered |
| E7/E8 examples “Expiry date” / “DOM”, unlabelled header cell E6 | Required interpretation of supplied date | `inventory_receipt.date_kind` | Separate explicit Expiry/DOM label; DOM never triggers expiry warning |
| F6 Batch number | Batch field | `inventory_receipt.batch_number` / matching item signature | Batch retained separately across receipts/prices/dates |
| G6 Updated by (name of person) | Defaults to submitting account; responsible name if different | `inventory_receipt.updated_by_account`, `.updated_by_name` | Responsible name plus actual submitting user/audit |

Additional owner fields: per-container price, stock/dose unit conversion, remaining quantity/value, combined restriction days and separate batch/date/price stock items. Report inventory quantities and stored receipts/postings, not just mutable current rows.

## Excluded and support sheets

| Sheet/content inspected | Disposition |
|---|---|
| `INSTRUCTIONS` (22 nonempty cells) | Guidance/provenance. A20 stray `ter` is excluded. Not a data-entry section. |
| `1`, `1A`, `1B` | Property risk assessment maps/documentation excluded. Example map inspected only as source context. |
| `3A`, `3B` | Grain/fodder and crop/pasture/paddock chemical treatments excluded; no hidden field expansion from these sheets. |
| `4` | Transport/dispatch preparation excluded by owner. |
| `7A` including embedded section `7B` at row 125 | All biosecurity/Johne's plan fields excluded. There is no separate worksheet named `7B` in this workbook. |
| `7C`, `8` | Visitors/training records excluded. |
| `Additional` | Empty support worksheet; no requirements. |
| hidden `DATA` | 4,745 sequential Excel date serials 44378–49122 and six lookup entries (`Yes`, `No`, `Review in 12 months`, `Note known risks`, `Expiry date`, `DOM`). All read; treat as validation support, not transactions or date limits for the new application. |

## Coverage checks to implement

Create a synthetic full-field record for each included section, export PDF and XLSX, and assert every mapped value and owner-override label survives. Check repeated treatment form blocks do not create duplicate fields; performer/calibrator contact and the inferred equipment date remain separate. Verify birth/death exceptions, missing data, dates/timezones and mixed breed/sex groups are represented without fabricated values. Preserve statutory/compliance caveats from the source: field coverage alone is not certification that StockLOG satisfies every regulatory obligation.
