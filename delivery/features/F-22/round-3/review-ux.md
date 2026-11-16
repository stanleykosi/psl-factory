VERDICT: PASS
COMMIT: de541608e755eb9de9b2625187c08abc297a3fb1
REVIEWER: reviewer-ux
AUTHORITY: delivery UX review

## Summary
- Reviewed the diff 0cc0a73b..de541608 (StepForm, Workspace, W-2209 fixture, tests) and checked W-2209 running at 390 width.
- "Edit your update" now opens with the saved words and the saved cites shown in all four pickers; focus lands on the form heading; the closed page is unchanged.
- The uncertain-without-reconcile state reads "We are checking what happened. Nothing was sent again." with one Reload button and no send or answer control (from code and the component tests; no fixture serves it in the browser).

## Findings
- UX-3-1 | non-blocking | low | frontend | Edit form, cite pickers with several saved records (status, next steps): the closed picker truncates the joined labels ("Milestone 2 · UAT signed 11 Nov, UAT walkt…"), so the PM cannot see all saved cites without opening it. Fix: show saved cites as chips or wrap the text.

## Verified
- QA-2-1 | verified | W-2209 edit form shows saved cites in all four pickers; test asserts all eight inputs on an unchanged send
- QA-2-3 | verified | code: sentence and Reload only for `effect_uncertain` without `reconcile`, hidden when the in-session notice is up; component tests cover both cases
