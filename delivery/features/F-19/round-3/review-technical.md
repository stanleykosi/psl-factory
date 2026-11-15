VERDICT: PASS
COMMIT: 95903eeb853bc2c9a244eb2e4d19174871d875de
REVIEWER: reviewer-technical
AUTHORITY: delegated technical review

## Findings
- none

## Notes
- Focus effect (BillingContactForm.tsx): `notice` starts null and is set only in the press handler, so nothing is focused on load. The effect only calls `.focus()` and sets no state, so it can't loop. It re-runs only when a new notice object is set, which is once per press. The `saved` and `invalid` kinds are excluded, so the invalid-field focus and the role=status path are unchanged.
- The diff adds assertions only; none removed or weakened. CSS adds scroll-margin and outline-offset only.
