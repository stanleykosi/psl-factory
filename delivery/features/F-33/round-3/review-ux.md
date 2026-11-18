VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: d20fd9b2ccee7be267936cc2758358989ecdedbb
AUTHORITY: delivery UX review

## Summary
- Re-walked W-2701..W-2712 as finance_lead at 1440 and 390 on :4883. No horizontal scroll at either width, and no dead ends. The states and wording match round 2, and W-2707 still shows "Unknown" with no zero.
- The Decide panel reads cleanly: "Note (needed to return or reject)", then the three buttons, then two small-print consequences. W-2702 now states what Reject does.
- On W-2712, Approve, Return (with a note) and Reject each leave the page in a clear unsettled state at both widths. Nothing reads as success.
- The mock was reset after the decisions.

## Findings
None new. UX-2-1 (the "See all exceptions" button on the hold) is still open and non-blocking. It also appears on the W-2712 unconfirmed page at 390.

## Verified
- UX-2-2 | verified | W-2702 and W-2712 panels at 1440 say "Rejecting stops this schedule: it isn't used for October's accounts." beside the Approve line "Approving doesn't post anything...". The Reject consequence is real returned text, matching the build.
- UX-2-1 | still open, non-blocking | frame button unchanged; the build has flagged it to the frame owner.
- W-2712 approve | verified | The status chip becomes "DECISION NOT CONFIRMED" in the warning colour. The notice reads "Schedule v1: result not confirmed", followed by "We are checking what happened. Nothing was sent again." with a Reload button. The next step says "We are checking whether the decision was recorded." There is no "approved" text, no Verified state, and no decide buttons, so a retry is not offered.
- W-2712 return and reject | verified | Same result at 1440 and at 390 (the note is entered in the phone drawer first). The stations stay at "Review: Needs a person" and the word "returned" or "rejected" never appears. A Finance reader cannot mistake it for success.
- Wording | verified | "Result not confirmed" is plain and warning-toned. "Nothing was sent again" is slightly ambiguous but acceptable.
- Previous notices | verified | The step notice is replaced, and the decide shows only its own outcome. Return without a note still shows "Add a note to return it."
- Phone | verified | The bottom bar opens a drawer with a labelled note field and Cancel. W-2703 shows the returned quote with its tint and "Stopped" at Review.
