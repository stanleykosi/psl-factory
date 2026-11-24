VERDICT: PASS
COMMIT: 7108be9d709378a1d14333db432515028e087aa0
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- Lighter panel (D-180): read the round-1 to round-2 diff of src/features/decide (LiveStates, DecideView, decide.css); no browser walk, and the builder's decide e2e (19 passed, axe clean) is the journey evidence.
- Stale compare is a real table with column and row headers, a visually hidden "Field" header and a text "changed/unchanged" mark, so the change is not colour alone.
- Phone stale view keeps the alert, the focus move to the heading and the review action; it shows the replaced line and the current card as on the board.
- The done "What happens next" panel is an aside named by its heading; the title is no longer drawn twice and the sub-line returns when it differs.
- No journey, state or permission path changed; no dead ends added.

## Findings
None.

## Verified
- UX-1-none | verified | round 1 had no findings to retest

## Pre-merge re-confirm (7108be9d)
VERDICT: PASS
Diff 9b921ea7..7108be9d is 15 files, all in the project pages, mock and tests (Delivery tab on the project, its model and hook, dlvov.css, project tab bar, mock delivery overview). No file under src/features/decide changed, and nothing in the diff references the decision desk.
The one shared change is the project tab bar: Delivery now sits after Journey on every project. That is on the project page, not the decision desk, and it matches the Delivery tab the spec names.
ledger-source.test.tsx changed only by a wait on the recorded notice, so no user-facing behaviour changed.
The round-2 decision desk findings and their evidence stand unchanged.
