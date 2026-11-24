VERDICT: PASS
COMMIT: 4ebb3c05b15901d845bcbef2d566dc27fa4b7e6a
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- Walked mock items 4120-4123 and 4110 at 1440 and 390 as the PMO/finance persona: "Check what happened", Resume, Cancel with its dialog, Pause and Continue background work all behave as the spec describes.
- Success shows as a toast (status, "Checked. This item is now: ..."), problems as a callout with a warning icon (409 and dropped connection checked); matches D-151.
- Cancel dialog ("Cancel this work?", "Keep it" / "Cancel this work") fits at 390, puts focus on "Keep it", closes on Escape and returns focus to the Cancel button.
- Locked state after an uncertain result: while the revision is unchanged both buttons are disabled with "Check the page before trying again."; it unlocks when the re-read shows a new revision (spec criterion 15).
- Carried fixes confirmed: breadcrumb reads "Invoice" / "Weekly report" (plain line name) and the state tag sits right-aligned at 1440 (left under the title at 390). Controls row stacks full width at 390 with large targets.

## Findings
- UX-1-1 | non-blocking | low | frontend | While the controls are locked after an uncertain result, the pressed button still reads "Working..." with the spinner, though nothing is running. Expected: its normal label (Resume) with the sentence; seen at 1440 and 390 on /work/4121 with scenario wdrop. frontend/src/features/work-item/live/ItemControls.tsx
- UX-1-2 | non-blocking | low | frontend | After a dropped connection where the re-read shows a new revision, the page shows "Ready to continue" and the callout "We couldn't confirm that this happened..." together, and Resume and Cancel stay enabled (the mock still lists them). Acceptable per the spec; consider clearing the callout once the re-read has settled so it does not contradict the tag.

## Verified
None. Round 1.
