# Cattle selection and direct-save workflows

Based on main at `484d2326e14ed7e359b65595494dbbb7d4c3a8d2`.

The cattle entry result uses the shared homepage button class for its three
destinations. Return to Active Cattle retains the server session's property/PIC.

Bulk Edit and Cattle Exit start with checkboxes on Active Cattle. Next posts
the permanent UUIDs to the destination workflow. The server validates their
current property/PIC, active status, identifier and on-farm presence, then signs
the exact IDs and presence periods with the actor, context and purpose. The
selected list replaces editable pickers. No large selection is placed in a URL.
Eligibility and presence snapshots are checked again inside the existing
property-locked transaction. Existing preview version checks and withholding
acceptance remain, as do idempotent confirmation retries.

Bulk Update Mob is an assignment to the selected cattle, never a source mob
used to expand the cohort. Unchecked update controls are ignored server-side.
Each update control and its field/help text share one responsive grid item.

Individual edits submit directly through the existing EditForm and
services.execute. Validation errors retain input and open the editor. Successful
saves return to the stable animal URL, refresh the summary, and retain lifetime
events and audit records. A stable form submission key protects normal retries.

## Version and compatibility

Propose **0.3.0**, a minor bump from **0.2.4** under AGENTS.md and the update policy:
this adds compatible selection workflows and bulk mob assignment. There are no
schema migrations, runtime dependency, installer or service changes and no
reinstall requirement. Recheck main's version and the v0.3.0 tag before an
approved merge. Merging, tagging, release publication and deployment require
separate approval.

## Verification

The attached Cloud workspace failed to recover: its exec-server connection
timed out. No shell, database or browser run was possible in that workspace.
Implementation is being verified through the repository's existing GitHub
Actions MariaDB/Chromium and isolated installer jobs. CI results will be recorded
in the PR once the run completes. No live server or real records are used.

Regressions cover direct saves and audit/identifier history; exact selection,
empty/malformed/duplicate/stale/inactive/out-of-scope IDs; actor/context/purpose
binding; changed farm periods; role revocation; retired/foreign mobs; checked and
unchecked mob assignment; restriction warnings; preview version checks; and
confirmation retries. Browser checks cover confirmation button styling and
destinations, disabled Next/other actions, both exit entry points, fixed selected
lists, and field/checkbox grouping at desktop and mobile widths. Browser
screenshots are written into the CI artifact's cattle-workflows directory.
