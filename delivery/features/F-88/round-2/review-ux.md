VERDICT: PASS
COMMIT: eacdc7045a458039ad42eb19ea5852cc411578df
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux (lighter panel, D-180)

## Summary
- Re-walked SCR-23 (Log RFP from Start work) and SCR-24 (Assign PM from My work, Unassigned) on the mock as the PMO Lead at 1440 and 390; no horizontal overflow, no dead ends.
- SCR-23 now shows the PRE-SALE eyebrow, the "pre-engagement workspace" callout, board labels and hints, and the four-way submission control. Empty submit lists 5 fixes with inline messages at both widths. The line shows in the chooser only because the mock `/lines` lists it.
- SCR-24 shows the callout, "2 people can prepare RFPs here" and the role hint; empty submit lists 4 fixes. The "What happens next" block stays.
- UX-1-1 is fixed for sighted users (no visible repeated heading). One smaller remainder: each run of lines still carries a visually hidden "Lines you can start" legend, so a screen reader hears it twice. UX-1-2 is untouched and carried forward.

## Findings
- UX-2-1 | non-blocking | low | frontend | The chooser splits the lines into runs around the unavailable ones, and each run is a radio group with the same hidden legend "Lines you can start", so assistive tech hears the same group name twice. Expected a distinct name per run, or one group. `frontend/src/features/start-work/LineChooser.tsx:137`.
- UX-1-2 | non-blocking | low | frontend | Carried forward, unchanged. The mock Unassigned tab badge and "6 records you can see" line disagree with the 13 rows in the received-bids list; build.md leaves it, and live `/work` has no counts. `frontend/src/features/my-work/MyWork.tsx`.

## Verified
- UX-1-1 | verified | At 1440 and 390 the chooser shows one visible "Lines you can start · 2" count and no repeated visible heading; Log a received RFP is listed only because `/lines` serves it. The hidden legend repeat is UX-2-1.
