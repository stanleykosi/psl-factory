VERDICT: PASS
COMMIT: b9c62eb095afab1a2df87f562ffef833678e021c
REVIEWER: reviewer-ux
AUTHORITY: delivery UX review

## Summary
- UX-1-1 is fixed: milestones, registers (empty and no-match) and actions now show one sentence through `TabEmpty`, with "Clear search" kept; a test asserts the sentence appears once.
- UX-1-2: accepted as not changed. SCR-29 desktop and phone draw "04 Nov" and the boards win.
- The round 1 to round 2 diff (read from code and tests, no servers run) changes layout CSS, the empty-state markup, the invoice cell (a missing or unlisted state now reads Unknown, with a test) and drops the `caseId` prop in favour of `journey.case_id`. Routes, URL state, links, paging, access states and error states are untouched.

## Findings
- UX-2-1 | non-blocking | `TabParts.tsx` `TabEmpty` | The empty sentence is now an `h3` directly under the page `h1` and the table caption level, so the heading outline may skip a level. | Use the same level as the other panel headings (h2), or a paragraph.

## Verified
- UX-1-1 | verified | `TabEmpty` in `MilestonesTab.tsx`, `RegistersTab.tsx` and `ActionsTab.tsx` renders the sentence once; `project-tabs.test.tsx` "shows the empty sentence once" passes per the builder's run.
- UX-1-2 | verified | not changed, accepted: SCR-29-desktop draws "04 Nov".
- UX-1-3 | verified | accepted as the approved Conflicts 11 exception.
