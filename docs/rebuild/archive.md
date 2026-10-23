# Legacy preservation and inspection

## Preserved revision

Full legacy HEAD: `cf1c9c0244462d39a398875c7f8f228fde4a3deb` (`Add files via upload`).

Archive branch: `archive/legacy-desktop-2026-10-23`, pointing exactly to that revision. Rebuild branch: `rebuild/web-replacement`, created from it. The incoming cloud checkout was on local branch `work`; it was clean. No reset, history rewrite or legacy file deletion was used. An archive branch preserves the entire ancestor history.

An additional complete-history recovery bundle was created outside the checkout at `/workspace/stocklog-rebuild-research/StockLOG-legacy-cf1c9c0.bundle`; `git bundle verify` passed. The bundle is local recovery material, not a published backup. Neither branch nor bundle has been pushed. Keep the archive ref intact when publishing the rebuild branch later; remote durability has not yet been established.

Inspection commands:

```sh
git rev-parse HEAD
git status --porcelain=v1
git log -5 --oneline
git show-ref --verify refs/heads/archive/legacy-desktop-2026-10-23
git bundle verify /workspace/stocklog-rebuild-research/StockLOG-legacy-cf1c9c0.bundle
git diff archive/legacy-desktop-2026-10-23 -- App Config
```

## Applicable instructions and repository evidence

No `AGENTS.md` exists at `/AGENTS.md`, `/workspace/AGENTS.md`, in the StockLOG checkout or its descendants at inspection. `/workspace/.agents` is empty. No repository-specific agent rules were found. The supplied documents are requirements sources, subordinate to this task's explicit preparation-only boundary; their references to implementation and PR delivery are future work.

The checkout contains eight PyQt5 view modules, `App/main.py`, two merge script versions, SQLite schema creation, a bulk merge utility, a summary and an empty settings template. There is no README, dependency manifest/lock, version pin, migration system, CI configuration, hosting entry point or existing automated test suite. Inspection covered file inventory, UI classes/workflows, SQL schema, storage paths and merge dispatch/services. The old summary is descriptive, not authoritative.

Legacy risks informing replacement: literal Windows data/script paths, NAS-specific schema path, replaceable identifier used as database primary key, REAL quantities/money, direct UI SQL writes, no authentication/property scoping and no durable event-time memberships. The flat JSON merge dispatcher classifies records containing `nlis_id`/`mob` as chemical logs before reaching cattle handling. No legacy fix or migration is proposed here. All existing `App/` and `Config/` bytes remain identical to the archive revision.

The old onboarding virtualenv and sample local database outside the checkout are unrelated to the replacement. Do not ingest them into the new production database. Future cloud tasks should use this existing checkout; no worktree is needed unless requested.
