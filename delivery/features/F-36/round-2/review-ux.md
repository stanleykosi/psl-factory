VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: 5e14a6ada5bd803586a0ced36e05176e8f84f66c
AUTHORITY: delivery UX review

## Summary
- Verification of 264b3492..5e14a6ad: four files, all scoped to `.rfp-assign` or the assign drawer; F-30 and F-31 forms unchanged. Vitest on rfp-assign and related files: 5 files, 137 tests passed at head 5e14a6ad.
- UX notes addressed with frontend-owned wording only.

## Findings
None.

## Verified
- UX-1-1 | verified | 422 on person_id/note/acting_role/evidence_id shows the page's own sentences (`ASSIGN_PM_TEXT.fieldMessage`); test and e2e assert them.
- UX-1-2 | verified | duplicate `ariaLabel` removed from the form in AssignPmDrawer.tsx.
- UX-1-3 | verified | after an unconfirmed write, 'Not confirmed at first; confirmed after reading it again.' shows under 'Assigned to <name>'; test asserts it.
