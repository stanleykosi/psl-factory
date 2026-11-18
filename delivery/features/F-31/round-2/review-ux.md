VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: 83747e368e5af5b4680839ede43bd485d8744414
AUTHORITY: delivery UX review

## Summary
- Re-walked W-2601 to W-2603 at 1440 and 390 (production build, mock on 4862, reset afterwards). Confirm PM, Register engagement and Record input all run through. No sideways scroll at either width.
- The lost-reply case (`record-then-fail`) now closes the Drawer onto the page with "QA is no longer waiting. We've reloaded this item so you can see whether it was recorded." The table behind shows QA as "IN · 11 DEC", so the wrong-team risk from UX-1-1 is gone. The normal path shows "Recorded under your name: QA's input" with the re-read row.
- Phone Record Drawer without Cancel: acceptable. The "x" Close is always visible at the top right of the sheet (44px), and Escape also closes it and returns focus to the Record input row button. A sticky Record input bar is below, so the PM is never trapped. A PM on a touch phone has no Escape, so Close is the one exit, and it is easy to find and hit.
- No new blocking finding.

## Findings
1. UX-2-1 | non-blocking | low | frontend | Phone Drawers differ: the Register engagement Drawer at 390 still shows a "Cancel" button beside the primary one, while the Record input Drawer has only Close. Both exits work. Consider one rule for both when the frame is next touched.

## Verified
- UX-1-1 | verified | `record-then-fail` at 390 and 1440: Drawer closes, page says "QA is no longer waiting. We've reloaded this item so you can see whether it was recorded.", QA row reads IN · 11 DEC. No "Recorded under your name" notice in this path.
- UX-1-2 | verified | W-2603 disabled "Prepare readiness" reads as a disabled button (grey) at 1440 and keeps `aria-disabled`, matching "Who receives this?".
- UX-1-3 | carried forward | Confirm PM and Register still sit low on the phone page, per spec Conflicts 7; non-blocking, unchanged.
- UX-1-4 | verified | Price row reads "Costing v2 · ₦40,951,000.00" as one value at 390 on W-2601 to W-2603.
- UX-1-5 | carried forward | Native Received date field is the shared F-18 form; not part of this feature.
- TECH-1-1 | verified | In the normal run the "Recorded under your name: QA's input, 18 Nov 04:12" notice appears together with the re-read row change (QA IN · 11 DEC, Product and Infrastructure rows intact). Failed re-read is covered by the builder's test; I did not force a re-read failure in the browser.
