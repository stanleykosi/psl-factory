VERDICT: PASS
COMMIT: 43a3d5fcad8e0072a85bcab2625a446b88d037e6
REVIEWER: reviewer-ux
AUTHORITY: delivery UX review

## Summary
- Both round-1 UX findings fixed, checked live on a fresh production build (mock 4803, app 4804).
- Fix changes only the 422 wording and the phone close-on-moved-list behaviour; the rest of the journey carries forward unchanged from round 1.

## Findings
None.

## Verified
- UX-1-1 | verified | 422 (`invalid`) on phone sheet reads "Check these fields: To, Ends." with "This person can't take this delegation." under To; same code path serves the 1440 panel (also run, no raw keys).
- UX-1-2 | verified | 390 `uncertain_written`: sheet closes (no dialog), warning "The list changed while we were checking. Look for your delegation before adding it again." shows above the cards, new 01-03 Dec row visible. Reopen-with-Start-again taken from build.md/e2e, not re-driven.

## Merge check (head 43a3d5fc, merge of dlv-00 with F-26)
- `git diff 34c38e4e..43a3d5fc` touches no file under frontend/src/features/setup, frontend/src/app/setup, frontend/src/components, mock/delegations.mjs, the delegation fixtures or e2e/setup-delegation.spec.ts. Frontend changes are Money-tab files and 3 added lines in mock/server.mjs (money route). F-27 differences are delivery records only. My round-2 live check and verdict carry over unchanged.
