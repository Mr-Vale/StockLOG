# Preparation validation and limits

Date: 23 October 2026. Scope: repository preservation, source inspection, design and dependency feasibility. No replacement functionality has been implemented. No hosting deployment, NAS connection or live database operation was performed.

## Passed

- Initial checkout clean; full legacy commit `cf1c9c0244462d39a398875c7f8f228fde4a3deb` preserved on `archive/legacy-desktop-2026-10-23`.
- Rebuild branch `rebuild/web-replacement` created; legacy `App/` and `Config/` unchanged against the archive.
- Complete-history external Git bundle verified by `git bundle verify`; local only, no remote archive durability claim.
- All three supplied files accessible and copied byte-for-byte; [source SHA-256 manifest](evidence/supplied-files.json).
- Markdown sources read in full. Workbook ZIP parts parsed, all 18 sheets traversed, every nonempty value/formula read, drawing text inspected, raster map/navigation images inspected; included fields mapped to planned screen/database/report fields. Independent openpyxl nonempty-cell counts matched XML extraction for every sheet, including hidden DATA (4,751 cells). DATA's 4,745 sequential date values were checked for uninterrupted +1 increments, not mistaken for business records.
- Upstream PEP/Django source and PyPI metadata read; Python 3.9 end-of-life and Django 5.2 incompatibility verified rather than inferred from local interpreter availability.
- Isolated Python 3.12.14 environment installed/imported Django 5.2.18, ReportLab 5.1.0, openpyxl 3.1.5, defusedxml and tzdata. Minimal Django WSGI handler returned exact expected HTTP 200 response. ReportLab produced an in-memory PDF signature; a synthetic XLSX round-tripped through openpyxl. These are library probes, not StockLOG reports, app/browser tests or cPanel evidence.
- Decimal arithmetic independently checked April cost $10,818/P&L $9,182 and combined cost $32,454/P&L $27,546 against the original scenario. These calculations did not exercise application logic.

Machine-readable probe results: [dependency-probes.json](evidence/dependency-probes.json). Workbook structure evidence: [workbook-inventory.json](evidence/workbook-inventory.json).

## Failed or restricted checks, with diagnosis

| Check | Observed result | Diagnosis / required next step |
|---|---|---|
| mysqlclient 2.3.0 local installation | Source-build failure: no valid pkg-config target for mysqlclient/mariadb/libmariadb/perconaserverclient | Cloud lacks client development libraries. Install supported prerequisites during coding setup, then rerun; prove host's exact driver route separately. No unsafe verification bypass or unverified replacement driver was used. |
| Direct Python/Django/cPanel/HostGator docs domains | Proxy tunnel HTTP 403 | Research network policy. Python/Django evidence retrieved from maintainers' GitHub source; direct provider documentation/account verification outstanding. Not a host application failure. |
| openpyxl full workbook read | Warning: some data validation extensions unsupported | Read-only inspection succeeded. Never write the source workbook with this library; original bytes retained. Imported data in the future must be validated independently of Excel controls. |

No network policy was changed.

## Not run / external gates

- Direct hosting account checks: owner now reports HostGator Hatchling, Python 3.9.25, Passenger, Percona 5.7.44-48, working SSH/cron and mysqldump 5.7.44-48 plus cPanel export tools. These details have been recorded without contacting the host. Python WSGI support/SFTP, newer supported runtime or vendor maintenance, InnoDB/grants/trigger enforcement, resource limits and consistent automated export/restore remain unverified. Original Django proposal is incompatible with the specified MySQL 5.7 target.
- Replacement migrations, authentication, financial calculations, inventory services, concurrency, correction, idempotency or browser workflows: not implemented, so no passing-test claim.
- Real-engine companion scenario, all 13 edge-case branches, phone/desktop tests and two cohort PDF/XLSX report pairs: unrun.
- Server backups, authenticated archive transfer, NAS scheduler/pull, isolated restore and retention/purge: design only, unrun.
- Remote branch publication/PR/deployment or fresh-task restoration: not performed. Review package is local on the rebuild branch.

## Reproduce the preparation checks

From the existing checkout:

```sh
cd /workspace/StockLOG
git show-ref --verify refs/heads/archive/legacy-desktop-2026-10-23
git diff --exit-code archive/legacy-desktop-2026-10-23 -- App Config
git bundle verify /workspace/stocklog-rebuild-research/StockLOG-legacy-cf1c9c0.bundle
python --version
UV_CACHE_DIR=/workspace/stocklog-rebuild-research/uv-cache uv python list --only-installed
```

The disposable research virtualenv is outside the repository. Installation commands actually exercised (first combined attempt fails on diagnosed driver prerequisite; second independently validates the remaining libraries):

```sh
export UV_CACHE_DIR=/workspace/stocklog-rebuild-research/uv-cache
uv venv /workspace/stocklog-rebuild-research/venv
uv pip install --python /workspace/stocklog-rebuild-research/venv/bin/python \
  Django==5.2.18 mysqlclient==2.3.0 reportlab==5.1.0 openpyxl==3.1.5 defusedxml tzdata
uv pip install --python /workspace/stocklog-rebuild-research/venv/bin/python \
  Django==5.2.18 reportlab==5.1.0 openpyxl==3.1.5 defusedxml tzdata
```

Do not recreate an existing virtualenv blindly or interpret the failed first command as completed setup. These temporary probes do not replace the tested dependency locks and engine-specific CI planned for stage one. No database service was started for the rebuild.

Review requested: resolve the stack/target mismatch using the updated hosting decision before selecting stage-one implementation. Retaining MySQL 5.7 requires a backend/constraint/migration redesign; the original Python/Django stack requires compatible runtime and database versions. Known plan/tool details need not be supplied again. Enter any eventual secrets through secure configuration, never chat or Git.
