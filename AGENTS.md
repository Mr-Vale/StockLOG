# StockLOG agent instructions

## Before making changes

- Read the task prompt and inspect the relevant code, specifications, tests, and any instructions in the folders you will edit.
- Start with `README.md` for project orientation and links to maintained setup and testing instructions. For installation, updater, and release work, read `docs/operations/UPDATES.md`.
- Keep changes focused on the requested behaviour. Follow existing StockLOG conventions and reuse shared components and business logic where practical.

## Preserve StockLOG behaviour

- Preserve property and PIC access controls and role-based permissions. Enforce them on the server when reading or changing records.
- Preserve permanent animal identity, identifier history, and audit records. Keep recording events when changing how history is displayed.
- Preserve inventory rules and existing financial calculations, corrections, and records. Check for duplicate costs or revenue when changing how transactions are recorded or corrected.
- Preserve branding and responsive layouts. Reuse shared styles and controls for interface changes.

## Data and database changes

- Use test data and an isolated environment for development and migration checks. Keep credentials, production database exports, and backups out of commits and pull requests.
- For changes that affect stored data, explain the migration and compatibility impact in the pull request. Verify that existing records still work. Where relevant, include records with missing values and animals with multiple farm entry and exit periods.

## Verify changes

- Run the repository’s documented checks relevant to the change. Report what passed and what could not be verified.
- Check the normal user workflow and, where relevant, users with different permissions.
- For interface changes, check the affected pages at desktop and mobile widths.

## Branches, review, and releases

- When asked to open a pull request, start from the current `main` branch unless the task specifies a different base. Use a dedicated branch and summarise the changes and verification in the pull request.
- For an application change, read the current version from `stocklog/version.json` on `main` and assess the full change against `docs/operations/UPDATES.md`. Use a **patch** bump for a compatible bug fix or small UI change, a **minor** bump for a compatible feature, and a **major** bump for a change requiring a complete reinstall. Use the highest applicable bump and reset the lower version components.
- Explain the proposed version and any migration or updater implications in the pull request. Update `stocklog/version.json` and `CHANGELOG.md` before review. Flag uncertain updater compatibility for review before finalising the version. Documentation-only changes require a version bump only when a release is requested.
- Before merging, confirm the proposed version is still correct against `main` and its release tag is unused.
- After the approved merge and with approval to publish, tag the exact merged commit with the matching `vMAJOR.MINOR.PATCH` tag and publish it as the latest stable GitHub release. Verify that the tag, version file, and release notes agree so the updater can discover the release.
- Obtain separate approval before merging, publishing a release, deploying to the live server, wiping data, or reinstalling the server.
