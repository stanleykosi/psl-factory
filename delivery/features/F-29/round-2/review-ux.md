VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: 8d72b263470b8c40dfd1e6223d8ce5c486712092

## Summary
- Re-walked /projects/P-0101/documents/D-2901?v=2 at 1440 and 390 as pm (default, returned, amount-unknown) on the shared mock (4853), read only; no approve or return made.
- Layout fixes read well: Tola note is a compact info strip (avatar, name inline, her lines); "Edit as v3" is pinned on the phone with its reason; on the phone the flag sits under the sections; no counter. Lagoon Health is consistent across crumb, title and P-0101.
- Read-only code check of the diff 9a6dd8ea..48752f43: link URLs are filtered (isLinkUrl), a re-read notice with "Try again" shows when the return can't be confirmed. Nothing breaks spec, boards, security or accessibility.

## Verified
- UX-1-1 | not fixed, still non-blocking | "Ask Tola to draft v3" is still plain bold text with "Not available yet" beside it (desktop and phone), while "Edit as v3" is a grey disabled button. The board draws two buttons; low-impact, fix with the next touch.
- UX-1-2 | left open | needs a backend sentence for superseded versions; not built in the browser by design.
- UX-1-3 | verified | amount-unknown on the phone now reads "AMOUNTS: UNKNOWN"; the matching case still reads "MATCHES COST-0140 V2".
- UX-1-4 | verified | crumb, title and project use Lagoon Health on P-0101; the document moved there.

## Findings
- UX-2-1 | non-blocking | low | frontend | Carried from UX-1-1: the held "Ask Tola to draft v3" is not styled as a disabled button like "Edit as v3".

## Update for head 8d72b263 (diff 48752f43..8d72b263)
- The merge only brings F-28 (minutes end states): workspace frame files (Links.tsx project_tab link, Sections.tsx, labels.ts RECORD_ID export, proposals.ts, workspace.css stacked-table rules), mock/workspace.mjs (audience-specific `.next` sidecar), new W-2309 to W-2314 fixtures, F-28 tests, and additive notes in delivery/BACKEND-HANDOFF.md (+11 lines).
- No file F-29 changed was touched: documents feature, DocumentsTab, project-tabs mock, documents.mjs, server.mjs (E-DOCUMENT handling) and F-29 tests are identical to the reviewed head. mock-contract.test.ts was not changed by F-29.
- Coordinator checks on this head: delivery/checks.sh exit 0 (2226 tests), e2e document-review, minutes-end, minutes and project-tabs 93 of 93 passed.
- Verdict unchanged.
