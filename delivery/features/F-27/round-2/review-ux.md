VERDICT: PASS
COMMIT: 34c38e4e3da89ce7b0aa08d62d2ef23c6434b6b3
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
