VERDICT: PASS
COMMIT: 67314929e5dd7b386dfc97494c7dbcfc0f87df9a
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux (lighter panel, D-180)

## Summary
- Re-walked SCR-23 (Log RFP from Start work) and SCR-24 (Assign PM from My work, Unassigned) on the mock as the PMO Lead at 1440 and 390; no horizontal overflow, no dead ends.
- SCR-23 now shows the PRE-SALE eyebrow, the "pre-engagement workspace" callout, board labels and hints, and the four-way submission control. Empty submit lists 5 fixes with inline messages at both widths. The line shows in the chooser only because the mock `/lines` lists it.
- SCR-24 shows the callout, "2 people can prepare RFPs here" and the role hint; empty submit lists 4 fixes. The "What happens next" block stays.
- UX-1-1 is fixed for sighted users (no visible repeated heading). One smaller remainder: each run of lines still carries a visually hidden "Lines you can start" legend, so a screen reader hears it twice. UX-1-2 is untouched and carried forward.

- Merge delta (D-193, diff-only, no servers): range-diff 8692cf87..eacdc704 vs 811465d8..98eb07bb shows all 6 F-88 commits equal. Main touched only My work (F-125: live rows without a known kind now show the error state; a "Verified outputs" link under the heading, 44px target). Start work, Log RFP and Assign PM are untouched. The Unassigned tab reads its own list (UnassignedBids), not /work, so the F-125 guard does not reach it; the new link is hidden from no persona and does not change the tab order of F-88 controls. My earlier verdict stands.
- Merge delta 2 (D-193, diff-only, no servers): range-diff 811465d8..98eb07bb vs f355d339..92045730 shows all 6 F-88 commits equal. Main added F-64 (decide desk under features/decide and decide-v7, mock live-decide, e2e decide specs) and checks.sh; none of it touches start-work, rfp, or My work, so Start work, Log RFP, the Unassigned tab and Assign PM are unchanged. Verdict stands.
- Merge delta 3 (D-193, diff-only, no servers): range-diff f355d339..92045730 vs 90748de3..67314929 shows every F-88 commit equal. Main added F-61 alerts; outside the alerts feature it only changes the bell counts in shell/AppShell.tsx (3 lines). Start work, Log RFP, the Unassigned tab and Assign PM are untouched. Verdict stands.

## Findings
- UX-2-1 | non-blocking | low | frontend | The chooser splits the lines into runs around the unavailable ones, and each run is a radio group with the same hidden legend "Lines you can start", so assistive tech hears the same group name twice. Expected a distinct name per run, or one group. `frontend/src/features/start-work/LineChooser.tsx:137`.
- UX-1-2 | non-blocking | low | frontend | Carried forward, unchanged. The mock Unassigned tab badge and "6 records you can see" line disagree with the 13 rows in the received-bids list; build.md leaves it, and live `/work` has no counts. `frontend/src/features/my-work/MyWork.tsx`.

## Verified
- UX-1-1 | verified | At 1440 and 390 the chooser shows one visible "Lines you can start · 2" count and no repeated visible heading; Log a received RFP is listed only because `/lines` serves it. The hidden legend repeat is UX-2-1.
