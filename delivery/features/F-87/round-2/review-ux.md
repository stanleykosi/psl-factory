VERDICT: PASS
COMMIT: a960d20decf30c113e2a4a9eedcff80949ac3202
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- Re-walked mock items 4120 to 4123 at 1440 and 390: Check what happened, Resume, Cancel with its dialog, Pause and Continue background work all behave as the spec describes; no horizontal overflow at 390.
- UX-1-1 is fixed: after an uncertain 500 on Resume, the locked button keeps its normal label "Resume" (disabled) with "Check the page before trying again." beside it, at both widths.
- Cancel now has the red reject outline style at both widths; the dialog ("Cancel this work?", "Keep it" / "Cancel this work") opens with focus on "Keep it" and Escape returns focus to Cancel.
- Success reads "Checked. This item is now: ..." / "Done. This item is now: ..." as a status; the dropped-connection callout is shown with the warning icon.
- Only the pressed command is locked (spec line 72), so Cancel stays available while Resume is locked; this matches the spec.

## Findings
- UX-1-2 | non-blocking | low | frontend | (carried, unchanged) After a dropped connection where the re-read shows a new revision, the page shows "Ready to continue" and the "We couldn't confirm that this happened..." callout together, with Resume and Cancel enabled. Spec-mandated message; consider clearing the callout once the re-read has settled.

## Verified
- UX-1-1 | verified | /work/4121 with scenario w500 at 1440 and 390: Resume disabled, label "Resume", sentence beside it; no "Working..." (it shows only while the request is running).
