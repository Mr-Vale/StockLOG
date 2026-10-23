> Implementation was subsequently authorised. This document records preparation decisions; current status, tests and the sole native Debian 13/Caddy deployment are in [the implementation checklist](../IMPLEMENTATION.md) and [operational installation guide](../operations/INSTALL.md). HostGator/cPanel, Python 3.9, MySQL 5.7 and Ubuntu deployment compatibility are superseded requirements.

# StockLOG replacement: preparation for review

Prepared 23 October 2026. Status: design proposal; no replacement application code or migrations implemented.

The current user request authorises archival, a rebuild branch, storing the supplied files, capability research and design. The attached implementation prompt describes the eventual delivery, but does **not** authorise implementing its later stages in this task. No deployment, NAS connection, live data access, hosting purchase, legacy migration or application replacement has been performed. The acceptance scenario's labelled synthetic assumptions remain test inputs rather than new business rules. Workbook sample people, products, doses and dates are examples, never installation seed data.

## Review package

- [Archive and repository inspection](archive.md)
- [Architecture decision](architecture.md)
- [Runtime and hosting evidence](runtime-hosting.md)
- [RackNerd VPS resource and operations plan](vps-deployment-plan.md)
- [Clean Debian 13 installer requirements](debian13-installation-contract.md)
- [Database design and transaction invariants](database-design.md)
- [LPA field-to-screen/database/report mapping](lpa-field-mapping.md)
- [Business-rule traceability and staged checklist](implementation-plan.md)
- [Validation and outstanding checks](validation.md)

Original supplied sources, preserved byte-for-byte:

- [Complete replacement specification](../specifications/StockLOG_rebuild_agent_prompt.md)
- [Independent acceptance scenario](../testing/StockLOG_acceptance_scenario.md)
- [May 2023 LPA workbook](../reference/may23-lpa-farm-records.xlsx)
- [SHA-256 source manifest](evidence/supplied-files.json)

Current proposed target: RackNerd KVM VPS, 2 GB RAM / 35 GB SSD / 2 vCPU. Recommend **Debian 13, Python 3.13, Django 5.2 LTS, MariaDB 11.8 InnoDB, Caddy, Gunicorn and systemd**. Ubuntu 24.04 with Python 3.12/MariaDB 10.11 is a compatible alternative. Caddy handles HTTP/HTTPS/static files; Gunicorn runs Django. Choose one OS/engine combination and test it before claiming support. The move supersedes the HostGator-specific Python 3.9/MySQL 5.7 restriction; preserve the [historical findings](hostgator-assessment.md), but do not carry that blocker into fresh-VPS development. Business rules are unchanged. See the [current hosting decision](runtime-hosting.md). Local probes are not VPS validation or application acceptance.

The owner now confirms the VPS has been set up with **Debian 13**, resolving the OS choice. Installed services have not been independently verified. Review the architecture and stage-one plan before authorising application implementation. Domain/TLS setup, application service installation, resource measurements, backups and restore remain future validation work. No credentials are requested. All three supplied files remain byte-for-byte unchanged.
