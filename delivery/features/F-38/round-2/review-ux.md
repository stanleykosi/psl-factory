VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: 273d81b5b7cb2d146cd010383cb6f5a40e9e6b96
AUTHORITY: delivery UX review

## Summary
- Re-walked W-3501 to W-3505 at 1440 and 390 as pm after a mock reset, including approve then "It didn't arrive". Nothing reads as submitted or sent before the re-read returns it; both round-1 blockers are fixed.

## Findings
- UX-1-3 | non-blocking | medium | frontend | Carried forward. The shared reconcile panel on the uncertain page still says "so the client is never invoiced twice" (1440) and "before anything is resent". Invoice wording on a submission pack; raise with the shared owner.
- UX-1-4 | non-blocking | low | frontend | Carried forward. The facts strip and station stepper are not on the SCR-40 boards; confirm with the design engineer that they are signed shared frame. Note that SENT reads "In progress" on uncertain and not-delivered pages, which is cautious and acceptable.
- UX-1-5 | non-blocking | low | frontend | Carried forward. Small targets: History 42x24 at 390.
- UX-1-6 | non-blocking | low | integration | Resolved for this round: the demo on 4985 now reaches the F-38 mock (W-35xx pages render the RFP items).

## Verified
- UX-1-1 | verified | After Approve, W-3505 shows "Next step. Delivery isn't confirmed yet. Someone checks it before anything is sent again.", "Document review: Done", "Submission: Needs a person", REVIEWED and APPROVED earned 26 Nov 14:58, SENT "In progress", and the timeline "Approved by document reviewer". After "It didn't arrive": "NOT DELIVERED", FAILED, "Someone checks with Tamarind Loans before anything is sent again", no Approve buttons and no resend. Same at 390. No "A document reviewer approves..." text remains.
- UX-1-2 | verified | W-3503 and W-3504 facts: Drafted 22 Nov 10:15, Reviewed and Approved 26 Nov 14:58, Sent 26 Nov 15:42, Receipt recorded and Verified 26 Nov 15:43, matching the timeline. Uncertain pages show no Receipt or Verified time.
- Before the re-read: W-3502 still shows "IN REVIEW" with Approve, Return and Reject; Submitted, Record the outcome and Sent-to RECEIVED appear only on W-3503/W-3504 and after the re-read. Uncertain page shows UNCERTAIN with "Time unknown", no Record the outcome and no send-again control.
- No overflow at 390 on any state.
