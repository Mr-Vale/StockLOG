# StockLOG replacement: preparation for review

Prepared 23 October 2026. Status: design proposal; no replacement application code or migrations implemented.

The current user request authorises archival, a rebuild branch, storing the supplied files, capability research and design. The attached implementation prompt describes the eventual delivery, but does **not** authorise implementing its later stages in this task. No deployment, NAS connection, live data access, hosting purchase, legacy migration or application replacement has been performed. The acceptance scenario's labelled synthetic assumptions remain test inputs rather than new business rules. Workbook sample people, products, doses and dates are examples, never installation seed data.

## Review package

- [Archive and repository inspection](archive.md)
- [Architecture decision](architecture.md)
- [Runtime and hosting evidence](runtime-hosting.md)
- [Database design and transaction invariants](database-design.md)
- [LPA field-to-screen/database/report mapping](lpa-field-mapping.md)
- [Business-rule traceability and staged checklist](implementation-plan.md)
- [Validation and outstanding checks](validation.md)

Original supplied sources, preserved byte-for-byte:

- [Complete replacement specification](../specifications/StockLOG_rebuild_agent_prompt.md)
- [Independent acceptance scenario](../testing/StockLOG_acceptance_scenario.md)
- [May 2023 LPA workbook](../reference/may23-lpa-farm-records.xlsx)
- [SHA-256 source manifest](evidence/supplied-files.json)

Recommended stack: supported Python 3.12 latest patch, Django 5.2 LTS latest security patch, MariaDB 10.11/11.4 LTS or maintained MySQL 8.4 with InnoDB, Django's mysqlclient driver, server-rendered responsive pages, small browser JavaScript, ReportLab PDF and openpyxl XLSX. Exact production pins and deployment feasibility remain conditional on actual hosting capability evidence. Local probes are not hosting approval or application acceptance.

Review the architecture and stage-one plan before authorising application implementation. The only outside information needed now is the actual hosting plan's non-secret capability evidence; no credential values are requested.
